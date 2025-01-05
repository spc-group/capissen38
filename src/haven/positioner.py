import asyncio
import logging
import warnings
from functools import partial

import numpy as np
from bluesky.protocols import Locatable, Location, Movable, Stoppable
from ophyd_async.core import (
    CALCULATE_TIMEOUT,
    DEFAULT_TIMEOUT,
    AsyncStatus,
    CalculatableTimeout,
    StandardReadable,
    WatchableAsyncStatus,
    WatcherUpdate,
    observe_value,
)

log = logging.getLogger(__name__)


class Positioner(StandardReadable, Locatable, Movable, Stoppable):
    """A positioner that has separate setpoint and readback signals.

    When set, the Positioner **monitors the state of the move** using
    a strategy selected based on the Positioner's configuration
    (chosen in order):

    1. If *put_complete* is true, await the setpoint's ``set()``
       status to report being done.
    2. If the positioner has a *done* signal attribute, wait for this
       signal to reach the value of ``Positioner.done_value``.
    3. Wait for the readback to be close to the setpoint (following
       :py:func:`numpy.isclose`).

    Parameters
    ==========
    name
      The device name for this positioner.
    put_complete
      If true, wait on the setpoint to report being done.
    min_move
      If the readback is already within *min_move* from the commanded
      position during ``set()``, no movement will take place.

    """

    done_value = 1

    def __init__(
        self, name: str = "", put_complete: bool = False, min_move: float = 0.0
    ):
        self.min_move = min_move
        self.put_complete = put_complete
        super().__init__(name=name)

    def set_name(self, name: str, *args, **kwargs):
        super().set_name(name)
        # Readback should be named the same as its parent in read()
        self.readback.set_name(name, *args, **kwargs)

    def watch_done(
        self, value, done_event: asyncio.Event, started_event: asyncio.Event
    ):
        """Update the event when the done value is actually done."""
        log.debug(f"Received new done value: {value}.")
        if value != self.done_value:
            # The movement has started
            log.debug("Setting started_event")
            started_event.set()
        elif started_event.is_set():
            # Move has finished
            log.debug("Setting done_event")
            done_event.set()

    async def locate(self) -> Location[int]:
        setpoint, readback = await asyncio.gather(
            self.setpoint.get_value(), self.readback.get_value()
        )
        location: Location = {
            "setpoint": setpoint,
            "readback": readback,
        }
        return location

    @WatchableAsyncStatus.wrap
    async def set(
        self,
        value: float,
        wait: bool = True,
        timeout: CalculatableTimeout = CALCULATE_TIMEOUT,
    ):
        new_position = value
        self._set_success = True
        old_position, current_position, units, precision, velocity = (
            await asyncio.gather(
                self.setpoint.get_value(),
                self.readback.get_value(),
                self.units.get_value(),
                self.precision.get_value(),
                self.velocity.get_value(),
            )
        )
        # Check for trivially small moves
        is_small_move = abs(new_position - current_position) < self.min_move
        if is_small_move:
            return
        # Decide how long we should wait
        if timeout == CALCULATE_TIMEOUT:
            assert velocity > 0, "Mover has zero velocity"
            timeout = abs(new_position - old_position) / velocity + DEFAULT_TIMEOUT
        # Make an Event that will be set on completion, and a Status that will
        # error if not done in time
        reached_setpoint = asyncio.Event()
        done_event = asyncio.Event()
        started_event = asyncio.Event()
        # Start the move
        if hasattr(self, "actuate"):
            # Set the setpoint, then click "go"
            await self.setpoint.set(new_position, wait=True)
            set_status = self.actuate.trigger(wait=self.put_complete, timeout=timeout)
        else:
            # Wait for the value to set, but don't wait for put completion callback
            set_status = self.setpoint.set(
                new_position, wait=(wait and self.put_complete), timeout=timeout
            )
        if not wait:
            return
        # Decide on how we will wait for completion
        if self.put_complete:
            # await the set call directly
            done_status = set_status
        elif hasattr(self, "done"):
            # Monitor the `done` signal
            log.debug(f"Monitoring progress via ``done`` signal: {self.done.name}.")
            self.done.subscribe_value(
                partial(
                    self.watch_done, done_event=done_event, started_event=started_event
                )
            )
            aws = asyncio.gather(done_event.wait(), set_status)
            done_status = AsyncStatus(asyncio.wait_for(aws, timeout))
        else:
            # Monitor based on readback position
            aws = asyncio.gather(reached_setpoint.wait(), set_status)
            done_status = AsyncStatus(asyncio.wait_for(aws, timeout))
        # If we don't care to wait for the return value, we can end
        if not wait:
            return
        # Monitor the position of the readback value
        async for current_position in observe_value(
            self.readback, done_status=done_status
        ):
            yield WatcherUpdate(
                current=current_position,
                initial=old_position,
                target=new_position,
                name=self.name,
                unit=units,
                precision=int(precision),
            )
            # Check if the move has finished
            target_reached = current_position is not None and np.isclose(
                current_position, new_position
            )
            if target_reached:
                reached_setpoint.set()
                break
        # Make sure the done point was actually reached
        await done_status
        # Handle failed moves
        if not self._set_success:
            raise RuntimeError("Motor was stopped")

    async def stop(self, success=True):
        self._set_success = success
        if hasattr(self, "stop_signal"):
            await self.stop_signal.trigger()
        else:
            warnings.warn(f"Positioner {self.name} has no stop signal.")
