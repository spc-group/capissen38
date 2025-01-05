import uuid
from collections import OrderedDict, abc
from typing import Mapping, Sequence, Union

import numpy as np
from bluesky import plan_patterns
from bluesky import plan_stubs as bps
from bluesky import plans as bp
from bluesky.preprocessors import (
    __read_and_stash_a_motor,
    _normalize_devices,
    finalize_wrapper,
    pchain,
    plan_mutator,
    reset_positions_wrapper,
    run_wrapper,
    stage_wrapper,
)
from bluesky.protocols import EventPageCollectable
from bluesky.utils import Msg, single_gen
from ophyd import Device
from ophyd.flyers import FlyerInterface
from ophyd.status import StatusBase
from ophyd_async.core import TriggerInfo
from ophyd_async.epics.motor import FlyMotorInfo

__all__ = ["fly_scan", "grid_fly_scan"]


def reset_flyers_wrapper(plan, devices=None):
    """Return flyer devices to their initial positions and velocities
    prior to being prepared for flying.

    Parameters
    ----------
    plan : iterable or iterator
        a generator, list, or similar containing `Msg` objects
    devices : collection or None, optional
        If default (None), apply to all devices that are prepared by the plan.

    Yields
    ------
    msg : Msg
        messages from plan with 'read' and finally 'set' messages inserted

    """
    initial_positions = OrderedDict()
    if devices is not None:
        devices, coupled_parents = _normalize_devices(devices)
    else:
        coupled_parents = set()

    def insert_reads(msg):
        eligible = devices is None or msg.obj in devices
        seen = msg.obj in initial_positions
        if (msg.command == "prepare") and eligible and not seen:
            # Stash flyer position
            plan_bits = [
                __read_and_stash_a_motor(msg.obj, initial_positions, coupled_parents)
            ]
            # Stash flyer velocity
            if hasattr(msg.obj, "velocity"):
                plan_bits.append(
                    __read_and_stash_a_motor(
                        msg.obj.velocity, initial_positions, coupled_parents
                    )
                )
            return (pchain(*plan_bits, single_gen(msg)), None)
        else:
            return None, None

    def reset():
        blk_grp = f"reset-{str(uuid.uuid4())[:6]}"
        for k, v in initial_positions.items():
            if k.parent in coupled_parents:
                continue
            yield Msg("set", k, v, group=blk_grp)
        yield Msg("wait", None, group=blk_grp)

    return (yield from finalize_wrapper(plan_mutator(plan, insert_reads), reset()))


def fly_line_scan(detectors: list, *args, num, dwell_time):
    """A plan stub for fly-scanning a single trajectory.

    Parameters
    ==========
    detectors
      Flyables that will be trigger before the movers move.
    *args
      For one dimension, motor, start, stop. In general:

      .. code-block:: python

         motor1, start1, stop1,
         motor2, start2, stop2,
         ...,
         motorN, startN, stopN

      Motors can be any ‘flyable’ object.
    num
      Number of measurements to take.
    dwell_time
      How long, in seconds, for each measurement point.
    """
    # Calculate parameters for the fly-scan
    # step_size = abs(start - stop) / (num - 1)
    motors = args[0::3]
    starts = args[1::3]
    ends = args[2::3]
    # Set up motors in their taxi position
    prepare_group = uuid.uuid4()
    for obj, start, end in zip(motors, starts, ends):
        position_info = FlyMotorInfo(
            start_position=start,
            end_position=end,
            time_for_move=dwell_time * num,
        )
        yield from bps.prepare(obj, position_info, wait=False, group=prepare_group)
    # Set up detectors
    trigger_info = TriggerInfo(
        number_of_triggers=num, livetime=dwell_time, deadtime=0, trigger="internal"
    )
    for obj in detectors:
        yield from bps.prepare(obj, trigger_info, wait=False, group=prepare_group)
    yield from bps.wait(group=prepare_group)
    # Monitor the motors during their move
    for motor in motors:
        sig = motor.user_readback
        yield from bps.monitor(sig, name=sig.name)
    # Perform the fly scan
    flyers = [*motors, *detectors]
    kickoff_group = uuid.uuid4()
    for flyer in flyers:
        yield from bps.kickoff(flyer, wait=False, group=kickoff_group)
    yield from bps.wait(group=kickoff_group)
    # Wait for all the flyers to be done
    motor_complete_group = uuid.uuid4()
    for m in motors:
        yield from bps.complete(m, wait=False, group=motor_complete_group)
    yield from bps.wait(group=(motor_complete_group))
    # Stop detectors
    det_complete_group = uuid.uuid4()
    for det in detectors:
        yield from bps.complete(det, wait=False, group=det_complete_group)
    yield from bps.wait(group=(det_complete_group))
    # Stop monitoring motors
    for motor in motors:
        sig = motor.user_readback
        yield from bps.unmonitor(sig)
    # Collect the data after flying
    flyers = [*motors, *detectors]
    flyers = [flyer for flyer in flyers if isinstance(flyer, EventPageCollectable)]
    for flyer_ in flyers:
        print(f"Collecting from {flyer_}")
        yield from bps.collect(flyer_)


def fly_scan(
    detectors: Sequence[FlyerInterface],
    *args,
    num: int,
    dwell_time: float,
    md: Mapping = {},
):
    """Do a fly scan with a 'flyer' motor and some 'flyer' detectors.

    Parameters
    ----------
    detectors
      List of 'readable' objects that support the flyer interface
    *args
      For one dimension, motor, start, stop. In general:

      .. code-block:: python

         motor1, start1, stop1,
         motor2, start2, stop2,
         ...,
         motorN, startN, stopN

      Motors can be any ‘flyable’ object.
    num
      Number of measurements to take.
    dwell_time
      How long, in seconds, for each measurement point.
    md
      metadata

    Yields
    ------
    msg
      'prepare', 'kickoff', 'complete, and 'collect' messages

    """
    # Stage the devices
    motors = args[0::3]
    starts = args[1::3]
    stops = args[2::3]
    # Prepare metadata representation of the motor arguments
    md_args = zip([repr(m) for m in motors], starts, stops)
    md_args = tuple(obj for m, start, stop in md_args for obj in [m, start, stop])
    # Prepare metadata
    md_ = {
        "plan_name": "fly_scan",
        "motors": [motor.name for motor in motors],
        "detectors": [det.name for det in detectors],
        "plan_args": {
            "detectors": list(map(repr, detectors)),
            "*args": md_args,
            "num": num,
            "dwell_time": dwell_time,
        },
    }
    md_.update(md)
    # Execute the plan
    line_scan = fly_line_scan(
        detectors,
        *args,
        num=num,
        dwell_time=dwell_time,
    )
    # Wrapper for reseting the initial motor position/velocity
    line_scan = reset_flyers_wrapper(line_scan, motors)
    # Wrapper for making it a proper run
    line_scan = run_wrapper(line_scan, md=md_)
    line_scan = stage_wrapper(line_scan, motors)
    yield from line_scan


def grid_fly_scan(
    detectors: Sequence[FlyerInterface],
    *args,
    snake_axes: Union[bool, Sequence[Device]] = False,
    md: Mapping = {},
):
    """Scan over a mesh with one of the axes collecting without stopping.

    Parameters
    ----------
    detectors
      list of 'readable' objects
    *args
      patterned like::

        motor1, start1, stop1, num1,
        motor2, start2, stop2, num2,
        ...
        flyer, flyer_start, flyer_stop, flyer_num

      The first motor is the "slowest", the outer loop. The last
      motor should be flyable.
    snake_axes
      which axes should be snaked, either ``False`` (do not snake any axes),
      ``True`` (snake all axes) or a list of axes to snake. "Snaking" an axis
      is defined as following snake-like, winding trajectory instead of a
      simple left-to-right trajectory. The elements of the list are motors
      that are listed in `args`. The list must not contain the slowest
      (first) motor, since it can't be snaked.
    md: dict, optional
      metadata

    Yields
    ------
    msg
      'stage', 'open_run', 'mv', 'kickoff', 'wait', 'complete, 'wait',
      'collect', 'close_run', 'stage' messages.

    """
    # Extract the step-scan vs fly-scan arguments
    *step_args, flyer, fly_start, fly_stop, fly_num = args
    # Handle giving snaked axes as a list
    step_chunks = list(plan_patterns.chunk_outer_product_args(step_args))
    num_steppers = len(step_chunks)
    motors = [m[0] for m in step_chunks]
    all_motors = [*motors, flyer]
    if isinstance(snake_axes, abc.Iterable) and not isinstance(snake_axes, str):
        snake_steppers = snake_axes.copy()
        try:
            snake_steppers.remove(flyer)
        except ValueError:
            snake_flyer = False
        else:
            snake_flyer = True
        # Save for metadata processing
        snaking = [
            (motor in snake_steppers) for motor, start, stop, num, snake in step_chunks
        ]
        snaking = (False, *snaking[1:], snake_flyer)
    else:
        snake_steppers = snake_axes
        snake_flyer = snake_axes
        snaking = [False, *[snake_axes for _ in step_chunks[1:]], snake_flyer]
    # Prepare metadata
    chunk_args = list(plan_patterns.chunk_outer_product_args(args))
    md_args = []
    motor_names = []
    for i, (motor, start, stop, num, snake) in enumerate(chunk_args):
        md_args.extend([repr(motor), start, stop, num])
        motor_names.append(motor.name)
    num_points = np.prod([num for motor, start, stop, num, snake in chunk_args])
    md_ = {
        "shape": tuple(num for motor, start, stop, num, snake in chunk_args),
        "extents": tuple(
            [start, stop] for motor, start, stop, num, snake in chunk_args
        ),
        "plan_args": {
            "detectors": list(map(repr, detectors)),
            "args": md_args,
        },
        "plan_name": "grid_fly_scan",
        "num_points": num_points,
        "num_intervals": num_points - 1,
        "motors": tuple(motor_names),
        "snaking": snaking,
        "hints": {},
    }
    # Add metadata hints for plotting, etc
    md_["hints"].setdefault("gridding", "rectilinear")
    try:
        md_["hints"].setdefault(
            "dimensions", [(m.hints["fields"], "primary") for m in all_motors]
        )
    except (AttributeError, KeyError):
        ...
    md_.update(md)
    # Set up the plan
    per_step = Snaker(
        snake_axes=snake_flyer,
        flyer=flyer,
        start=fly_start,
        stop=fly_stop,
        num=fly_num,
        extra_signals=motors,
    )
    grid_scan = yield from bp.grid_scan(
        detectors,
        *step_args,
        snake_axes=snake_steppers,
        per_step=per_step,
        md=md_,
    )
    grid_scan = reset_flyers_wrapper(grid_scan)
    grid_scan = reset_positions_wrapper(grid_scan)
    uid = yield from grid_scan
    return uid


class Snaker:
    """Executes 1-D fly line scans in a snaking motion.

    Each call of the snaker executes the same fly-scan, but supports
    alternating scan directions to save time.

    This callable's signature is compatible with bluesky's
    ``per_step`` option for scans, so instead of just reading a
    detector, a whole fly-scan is performed."

    """

    reverse: bool = False

    def __init__(self, snake_axes, flyer, start, stop, num, extra_signals):
        self.snake_axes = snake_axes
        self.flyer = flyer
        self.start = start
        self.stop = stop
        self.num = num
        self.extra_signals = extra_signals

    def __call__(self, detectors, step, pos_cache):
        # Move the step-scanning motors to the correct position
        yield from bps.move_per_step(step, pos_cache)
        # Determine line scans range based on snaking
        start, stop = (self.start, self.stop)
        if self.reverse and self.snake_axes:
            start, stop = stop, start
        self.reverse = not self.reverse
        # Launch the fly scan
        yield from fly_line_scan(
            detectors,
            self.flyer,
            start,
            stop,
            num=self.num,
            extra_signals=step.keys(),
        )


class FlyerCollector(FlyerInterface, Device):
    stream_name: str
    detectors: Sequence
    positioners: Sequence

    def __init__(
        self,
        detectors,
        positioners,
        stream_name: str = "primary",
        extra_signals=(),
        *args,
        **kwargs,
    ):
        # self.flyers = flyers
        self.detectors = detectors
        self.positioners = positioners
        self.stream_name = stream_name
        self.extra_signals = extra_signals
        super().__init__(*args, **kwargs)

    def kickoff(self):
        return StatusBase(success=True)

    def complete(self):
        return StatusBase(success=True)

    def collect(self):
        collections = [iter(flyer.collect()) for flyer in self.detectors]
        while True:
            event = {
                "data": {},
                "timestamps": {},
            }
            try:
                for coll in collections:
                    datum = next(coll)
                    event["data"].update(datum["data"])
                    event["timestamps"].update(datum["timestamps"])
            except StopIteration:
                break
            # Use the median time stamps for the overall event time
            timestamps = []
            for ts in event["timestamps"].values():
                timestamps.extend(np.asarray(ts).flatten())
            event["time"] = np.median(timestamps)
            # Add interpolated motor positions
            for motor in self.positioners:
                datum = motor.predict(event["time"])
                event["data"].update(datum["data"])
                event["timestamps"].update(datum["timestamps"])
            # Add extra non-flying signals (not inc. in event time)
            for signal in self.extra_signals:
                for signal_name, reading in signal.read().items():
                    event["data"][signal_name] = reading["value"]
                    event["timestamps"][signal_name] = reading["timestamp"]
            yield event

    def describe_collect(self):
        desc = OrderedDict()
        for flyer in [*self.positioners, *self.detectors]:
            for stream, this_desc in flyer.describe_collect().items():
                desc.update(this_desc)
        # Add extra signals, e.g. slow motor during a grid fly scan
        for signal in self.extra_signals:
            desc.update(signal.describe())
        return {self.stream_name: desc}


# -----------------------------------------------------------------------------
# :author:    Mark Wolfman
# :email:     wolfman@anl.gov
# :copyright: Copyright © 2023, UChicago Argonne, LLC
#
# Distributed under the terms of the 3-Clause BSD License
#
# The full license is in the file LICENSE, distributed with this software.
#
# DISCLAIMER
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# -----------------------------------------------------------------------------
