import asyncio
import inspect
import numbers
from functools import partial
from typing import Callable, Mapping, Optional, Sequence, Type

import numpy as np
from bluesky.protocols import Reading, Subscribable
from ophyd_async.core import (
    CALCULATE_TIMEOUT,
    DEFAULT_TIMEOUT,
    AsyncStatus,
    CalculatableTimeout,
    Callback,
    SignalBackend,
    Signal,
    SignalDatatypeT,
    SignalR,
    SignalRW,
    SignalX,
    SoftSignalBackend,
    T,
)
from ophyd_async.core._signal import _wait_for
from ophyd_async.epics.core._signal import _epics_signal_backend


class DerivedSignalBackend(SoftSignalBackend):
    """Links a signal to the values of one or more other signals.

    The argument *derived_from* gives the signals that will be used
    for deriving this signal. It should be a mapping of argument names
    to ophyd-async signals, and will be given as keyword arguments to
    the *inverse* and *forward* transforms.

    The default behavior will forward the set value to the real
    signals, and read the real signal's value back (or average of the
    signals if multiple are given).

    To customize this behavior, provide the *forward* or *inverse*
    arguments when creating this backend, or subclass this backend and
    override the ``forward()`` and ``inverse()`` methods.

    *forward()* should be an async function that accepts a positional
    argument with the value sent to this derived signal, along with
    keyword-only arguments corresponding to the signals indicated in
    *derived_from*. It should return a mapping of real signals
    to their new values.

    *inverse()* should accept a positional argument that is a mapping
    of real signals to their read value, along with
    keyword-only arguments corresponding to the signals indicated in
    *derived_from*. It should return a new value to will be sent to
    the derived signal.

    Parameters
    ==========
    derived_from
      From which other signals does this signal derive. Maps
      transformer arguments names to signals.
    forward
      Transforms the derived signal value to the real signal values.
    inverse
      Transforms the real signal values to the derived signals'
      values.

    """

    def __init__(
        self,
        *args,
        derived_from: Mapping,
        forward: Callable = None,
        inverse: Callable = None,
        **kwargs,
    ):
        self._derived_from = derived_from
        if forward is not None:
            self.forward = forward
        if inverse is not None:
            self.inverse = inverse
        self._cached_readings = {}
        super().__init__(*args, **kwargs)

    async def forward(self, value, **kw):
        """The default forward transform for derived signals.

        This method returns the same value for the real signals as was
        set to the derived signal. This behavior can be overridden
        either by subclassing this backend, or by providing a
        *forward* parameter when creating the backend object.

        """
        # Return the same value for the real signal as the derived signal.
        return {key: value for key in kw.values()}

    def inverse(self, values, **kw):
        """The default inverse transform for derived signals.

        This method returns the same value for the derived signal as
        was set for the real signal. If more than one *derived_from*
        signal was provided, this method will return the median. More
        sophisticated behavior can be specified either by subclassing
        this backend, or by providing a *inverse* parameter when
        creating the backend object.

        """
        # Determine a sensible inverse transform value if possible
        is_numeric = all(isinstance(val, numbers.Number) for val in values.values())
        if is_numeric:
            return np.median(tuple(values.values()))
        elif len(values) == 1:
            # Only one value, so return it as-is
            return list(values.values())[0]
        else:
            # No sensible value is possible
            msg = "Cannot determine inverse value for {self} from {values}. "
            msg += "Provide an explicit inverse transform."
            raise ValueError(msg)

    def source(self, name: str, read: bool):
        src = super().source(name, read)
        args = ",".join(self._derived_from.keys())
        return f"{src}({args})"

    async def _subscribe_child(self, child_signal):
        """Subscribe to a child signal for updating value changes.

        If *child_signal* is not yet connected, keep retrying until
        sucessful or the timeout value is reached.

        """
        handler = partial(self.update_readings, signal=child_signal)
        while True:
            try:
                child_signal.subscribe(handler)
            except NotImplementedError:
                await asyncio.sleep(0.01)
            else:
                break

    async def connect(self, timeout=DEFAULT_TIMEOUT) -> None:
        # Listen for changes in the derived_from signals
        sub_signals = self._derived_from.values()
        sub_signals = (sig for sig in sub_signals if isinstance(sig, Subscribable))
        subs = (
            asyncio.wait_for(self._subscribe_child(sig), timeout=timeout)
            for sig in sub_signals
        )
        await asyncio.gather(super().connect(timeout=timeout), *subs)

    def combine_readings(self, readings):
        timestamp = max([rd["timestamp"] for rd in readings.values()])
        severity = max([rd.get("severity", 0) for rd in readings.values()])
        values = {sig: rdg["value"] for sig, rdg in readings.items()}
        new_value = self.inverse(values, **self._derived_from)
        self.reading = Reading(
            value=self.converter.write_value(new_value),
            timestamp=timestamp,
            alarm_severity=severity,
        )
        return self.reading

    def update_readings(self, reading, signal):
        """Callback receives readings from derived_from signals.

        Stashes them for later recall.

        """
        # Stash this reading
        self._cached_readings.update({signal: reading[signal.name]})
        # Update interested parties if we have a full set of readings
        self.send_latest_reading()

    def send_latest_reading(self):
        """Force this backend to send the latest readings to the callback."""
        # Update interested parties if we have a full set of readings
        readings = self._cached_readings
        missing_signals = [
            sig for sig in self._derived_from.values() if sig not in readings.keys()
        ]
        if len(missing_signals) == 0:
            # We have all the readings, so update the cached values
            new_reading = self.combine_readings(readings)
            if self.callback is not None:
                self.callback(new_reading)

    def set_callback(self, callback: Callback[Reading[SignalDatatypeT]] | None) -> None:
        super().set_callback(callback)
        self.send_latest_reading()

    async def put(self, value: Optional[T], wait=True, timeout=None):
        write_value = (
            self.converter.write_value(value)
            if value is not None
            else self.initial_value
        )
        # Calculate the derived set points
        new_values = await self.forward(write_value, **self._derived_from)
        # Set the new values
        aws = []
        for sig, val in new_values.items():
            if isinstance(sig, SignalX):
                # SignalX objects can't be set, so it must have been triggered
                aws.append(sig.trigger(wait=wait, timeout=timeout))
            else:
                # Check that the independent signal accepts "wait" args
                params = inspect.signature(sig.set).parameters
                kw = {}
                if "wait" in params:
                    kw["wait"] = wait
                aws.append(sig.set(val, timeout=timeout, **kw))
        await asyncio.gather(*aws)

    async def get_reading(self) -> Reading:
        signals = self._derived_from.values()
        readings = await asyncio.gather(*(sig.read() for sig in signals))
        readings = {sig: reading[sig.name] for (sig, reading) in zip(signals, readings)}
        # Return a proper reading for this derived value
        return self.combine_readings(readings)


def derived_signal_rw(
    datatype: Optional[Type[T]],
    *,
    initial_value: Optional[T] = None,
    name: str = "",
    derived_from: Mapping[str, Signal],
    forward: Callable = None,
    inverse: Callable = None,
    units: str | None = None,
    precision: int | None = None,
) -> SignalRW[T]:
    """Creates a signal linked to one or more other signals.

    The argument *derived_from* gives the existing signals that will
    be used for deriving this signal. It should be a mapping of
    argument names to ophyd-async signals, and will be given as
    keyword arguments to the *inverse* and *forward* transforms
    describe below.

    The default behavior will forward the set value to the real
    signals, and read the real signal's value back (or average of the
    signals if multiple are given).

    To customize this behavior, provide the *forward* or *inverse*
    arguments when creating this backend, or subclass this backend and
    override the ``forward()`` and ``inverse()`` methods.

    *forward()* should be an async function that accepts a positional
    argument with the value sent to this derived signal, along with
    keyword-only arguments corresponding to the signals indicated in
    *derived_from*. It should return a mapping of real signals
    to their new values.

    *inverse()* should accept a positional argument that is a mapping
    of real signals to their read value, along with
    keyword-only arguments corresponding to the signals indicated in
    *derived_from*. It should return a new value to will be sent to
    the derived signal.

    Example:

    .. code-block:: python

        async def squareroot(value, *, voltage):
            return {voltage: value**0.5}

        def square(values, *, voltage):
            return values[voltage]**2

        class MyDevice(Device):
            def __init__(self, prefix, name="", **kwargs):
                self.voltage = soft_signal_rw(int)
                self.voltage_squared = derived_signal_rw(
                    int,
                    derive_from={"voltage": self.voltage},
                    foward=squareroot,
                    inverse=square
                )
                super().__init__(name=name, **kwargs)

    Parameters
    ==========
    derived_from
      From which other signals does this signal derive. Maps
      transformer arguments names to signals.
    forward
      Transforms the derived signal value to the real signal values.
    inverse
      Transforms the real signal values to the derived signals'
      values.

    """
    backend = DerivedSignalBackend(
        datatype,
        derived_from=derived_from,
        forward=forward,
        inverse=inverse,
        initial_value=initial_value,
        units=units,
        precision=precision,
    )
    signal = SignalRW(backend, name=name)
    return signal


def derived_signal_r(
    datatype: Optional[Type[T]],
    *,
    initial_value: Optional[T] = None,
    name: str = "",
    derived_from: Mapping[str, Signal],
    inverse: Callable = None,
    units: str | None = None,
    precision: int | None = None,
) -> SignalRW[T]:
    """Creates a signal linked to one or more other signals.

    The argument *derived_from* gives the existing signals that will
    be used for deriving this signal. It should be a mapping of
    argument names to ophyd-async signals, and will be given as
    keyword arguments to the *inverse* transform describe below.

    The default behavior will read the real signal's value back (or
    average of the signals if multiple are given).

    To customize this behavior, provide the *inverse*
    arguments when creating this backend, or subclass this backend and
    override the ``inverse()`` methods.

    *inverse()* should accept a positional argument that is a mapping
    of real signals to their read value, along with keyword-only
    arguments corresponding to the signals indicated in
    *derived_from*. It should return a new value to will be sent to
    the derived signal.

    Example:

    .. code-block:: python

        def square(values, *, voltage):
            return values[voltage]**2

        class MyDevice(Device):
            def __init__(self, prefix, name="", **kwargs):
                self.voltage = soft_signal_rw(int)
                self.voltage_squared = derived_signal_r(
                    int,
                    derive_from={"voltage": self.voltage},
                    inverse=square
                )
                super().__init__(name=name, **kwargs)

    Parameters
    ==========
    derived_from
      From which other signals does this signal derive. Maps
      transformer arguments names to signals.
    inverse
      Transforms the real signal values to the derived signals'
      values.

    """
    backend = DerivedSignalBackend(
        datatype,
        derived_from=derived_from,
        inverse=inverse,
        initial_value=initial_value,
        units=units,
        precision=precision,
    )
    signal = SignalR(backend, name=name)
    return signal


def derived_signal_x(
    *,
    name: str = "",
    derived_from: Sequence,
    forward: Callable = None,
) -> SignalX:
    """Creates a signal linked to one or more other signals.

    The argument *derived_from* gives the existing signals that will
    be used for deriving this signal. It should be a mapping of
    argument names to ophyd-async signals, and will be given as
    keyword arguments to the *inverse* transform describe below.

    The default behavior will read the real signal's value back (or
    average of the signals if multiple are given).

    To customize this behavior, provide the *inverse*
    arguments when creating this backend, or subclass this backend and
    override the ``inverse()`` methods.

    *inverse()* should accept a positional argument that is a mapping
    of real signals to their read value, along with keyword-only
    arguments corresponding to the signals indicated in
    *derived_from*. It should return a new value to will be sent to
    the derived signal.

    Example:

    .. code-block:: python

        def square(values, *, voltage):
            return values[voltage]**2

        class MyDevice(Device):
            def __init__(self, prefix, name="", **kwargs):
                self.voltage = soft_signal_rw(int)
                self.voltage_squared = derived_signal_r(
                    int,
                    derive_from={"voltage": self.voltage},
                    inverse=square
                )
                super().__init__(name=name, **kwargs)

    Parameters
    ==========
    derived_from
      From which other signals does this signal derive. Maps
      transformer arguments names to signals.
    inverse
      Transforms the real signal values to the derived signals'
      values.

    """
    backend = DerivedSignalBackend(
        int,
        derived_from=derived_from,
        forward=forward,
    )
    signal = SignalX(backend, name=name)
    return signal


class SignalXVal(SignalX):
    trigger_value = 1

    def __init__(self, *args, trigger_value=1, **kwargs):
        self.trigger_value = trigger_value
        super().__init__(*args, **kwargs)

    @AsyncStatus.wrap
    async def trigger(
        self, wait=True, timeout: CalculatableTimeout = CALCULATE_TIMEOUT
    ) -> None:
        """Trigger the action and return a status saying when it's done"""
        if timeout == CALCULATE_TIMEOUT:
            timeout = self._timeout
        source = self._connector.backend.source(self.name, read=False)
        self.log.debug(f"Putting default value to backend at source {source}")
        await _wait_for(
            self._connector.backend.put(self.trigger_value, wait=wait), timeout, source
        )
        self.log.debug(f"Successfully put default value to backend at source {source}")


def epics_signal_xval(write_pv: str, name: str = "", trigger_value=1) -> SignalXVal:
    """Create a `SignalX` backed by 1 EPICS PVs. This differs from the
    standard ophyd-async trigger in that it accepts a prescribed
    *trigger_value* that will be sent to the PV when triggered.

        Parameters
        ----------
        write_pv:
          The PV to write its initial value to on trigger
        trigger_value:
          The value to send to the write PV.

    """
    backend: SignalBackend = _epics_signal_backend(None, write_pv, write_pv)
    return SignalXVal(backend, name=name, trigger_value=trigger_value)
