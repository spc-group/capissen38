"""Holds ion chamber detector descriptions and assignments to EPICS PVs."""

import asyncio
import logging
import warnings
from typing import Dict

from bluesky.protocols import Triggerable
from ophyd_async.core import (
    DEFAULT_TIMEOUT,
    AsyncStatus,
    StandardReadable,
    StandardReadableFormat,
    TriggerInfo,
    LazyMock,
    soft_signal_rw,
    wait_for_value,
)

from .labjack import LabJackT7
from .scaler import MultiChannelScaler
from .signal import derived_signal_r
from .srs570 import SRS570PreAmplifier

log = logging.getLogger(__name__)


__all__ = ["IonChamber"]


class IonChamber(StandardReadable, Triggerable):
    """A high-level abstraction of an ion chamber.

    Parameters
    ==========
    auto_name
      If true, or None when no name was provided, the name for
      this motor will be set based on the motor's *description*
      field.


    Sub-Devices
    ===========
    mcs
      A multi-channel scaler pointed to be *scaler_prefix*. This
      device will have two channels, the clock channel (#0) and the
      data channel, determined by *scaler_channel*.

    """

    _ophyd_labels_ = {"ion_chambers", "detectors"}
    _trigger_statuses: dict[str, AsyncStatus] = {}
    _clock_register_width = 32  # bits in the register

    def __init__(
        self,
        scaler_prefix: str,
        scaler_channel: int,
        preamp_prefix: str,
        voltmeter_prefix: str,
        voltmeter_channel: int,
        counts_per_volt_second: float,
        name="",
        auto_name: bool | None = None,
    ):
        self.scaler_prefix = scaler_prefix
        self._scaler_channel = scaler_channel
        self._voltmeter_channel = voltmeter_channel
        self.auto_name = auto_name
        with self.add_children_as_readables(StandardReadableFormat.CONFIG_SIGNAL):
            self.counts_per_volt_second = soft_signal_rw(
                float, initial_value=counts_per_volt_second
            )
        # Add the SRS570 pre-amplifier signals
        with self.add_children_as_readables():
            self.preamp = SRS570PreAmplifier(preamp_prefix)
        # Add the labjack voltmeter device
        self.voltmeter = LabJackT7(
            prefix=voltmeter_prefix,
            analog_inputs=[voltmeter_channel],
            digital_ios=[],
            analog_outputs=[],
            digital_words=[],
        )
        self.add_readables([self.voltmeter_channel.final_value])
        self.add_readables(
            [
                self.voltmeter.analog_in_resolution_all,
                self.voltmeter.analog_in_sampling_rate,
                self.voltmeter.analog_in_settling_time_all,
                self.voltmeter_channel.description,
                self.voltmeter_channel.device_type,
                self.voltmeter_channel.differential,
                self.voltmeter_channel.enable,
                self.voltmeter_channel.high,
                self.voltmeter_channel.input_link,
                self.voltmeter_channel.low,
                self.voltmeter_channel.mode,
                self.voltmeter_channel.range,
                self.voltmeter_channel.resolution,
                self.voltmeter_channel.scanning_rate,
                self.voltmeter_channel.temperature_units,
                self.voltmeter.device_temperature,
                self.voltmeter.driver_version,
                self.voltmeter.firmware_version,
                self.voltmeter.last_error_message,
                self.voltmeter.ljm_version,
                self.voltmeter.model_name,
                self.voltmeter.poll_sleep_ms,
                self.voltmeter.serial_number,
            ],
            StandardReadableFormat.CONFIG_SIGNAL,
        )
        # Add scaler channel
        self.mcs = MultiChannelScaler(
            prefix=scaler_prefix, channels=[0, scaler_channel]
        )
        self.add_readables(
            [
                self.mcs.scaler.channels[0].net_count,
                self.mcs.scaler.channels[0].raw_count,
                self.scaler_channel.net_count,
                self.scaler_channel.raw_count,
                self.mcs.scaler.elapsed_time,
            ],
            StandardReadableFormat.UNCACHED_SIGNAL,
        )
        self.add_readables(
            [
                self.mcs.acquire_mode,
                self.mcs.channel_1_source,
                self.mcs.channel_advance_source,
                self.mcs.count_on_start,
                self.mcs.dwell_time,
                self.mcs.firmware,
                self.mcs.input_mode,
                self.mcs.input_polarity,
                self.mcs.lne_output_delay,
                self.mcs.lne_output_polarity,
                self.mcs.lne_output_stretcher,
                self.mcs.lne_output_width,
                self.mcs.model,
                self.mcs.mux_output,
                self.mcs.num_channels,
                self.mcs.num_channels_max,
                self.mcs.output_mode,
                self.mcs.output_polarity,
                self.mcs.prescale,
                self.mcs.preset_time,
                self.mcs.snl_connected,
                self.mcs.scaler.clock_frequency,
                self.mcs.scaler.count_mode,
                self.mcs.scaler.delay,
                self.mcs.scaler.preset_time,
                self.mcs.scaler.channels[0].description,
                self.mcs.scaler.channels[0].is_gate,
                self.mcs.scaler.channels[0].offset_rate,
                self.mcs.scaler.channels[0].preset_count,
                self.scaler_channel.description,
                self.scaler_channel.is_gate,
                self.scaler_channel.offset_rate,
                self.scaler_channel.preset_count,
            ],
            StandardReadableFormat.CONFIG_SIGNAL,
        )
        # Add calculated signals
        self.net_current = derived_signal_r(
            float,
            name="current",
            units="A",
            derived_from={
                "gain": self.preamp.gain,
                "count": self.scaler_channel.net_count,
                "clock_count": self.mcs.scaler.channels[0].raw_count,
                "clock_frequency": self.mcs.scaler.clock_frequency,
                "counts_per_volt_second": self.counts_per_volt_second,
            },
            inverse=self._counts_to_amps,
        )
        self.add_readables(
            [self.net_current], StandardReadableFormat.HINTED_UNCACHED_SIGNAL
        )
        # Measured current without dark current correction
        self.raw_current = derived_signal_r(
            float,
            name="current",
            units="A",
            derived_from={
                "gain": self.preamp.gain,
                "count": self.scaler_channel.raw_count,
                "clock_count": self.mcs.scaler.channels[0].raw_count,
                "clock_frequency": self.mcs.scaler.clock_frequency,
                "counts_per_volt_second": self.counts_per_volt_second,
            },
            inverse=self._counts_to_amps,
        )
        self.add_readables([self.raw_current], StandardReadableFormat.UNCACHED_SIGNAL)
        super().__init__(name=name)

    def _counts_to_amps(
        self,
        values,
        *,
        count,
        gain,
        clock_count,
        clock_frequency,
        counts_per_volt_second,
    ):
        """Pre-amp output current calculated from scaler counts."""
        try:
            # Calculate the output voltage from the pre-amp
            time = values[clock_count] / values[clock_frequency]
            voltage = values[count] / values[counts_per_volt_second] / time
            # Calculate the input current from pre-amp gain
            return voltage / values[gain]
        except ZeroDivisionError:
            return float("nan")

    def __repr__(self):
        return (
            f"<{type(self).__name__}: '{self.name}' "
            f"({self.scaler_channel.raw_count.source})>"
        )

    @property
    def scaler_channel(self):
        return self.mcs.scaler.channels[self._scaler_channel]

    @property
    def voltmeter_channel(self):
        return self.voltmeter.analog_inputs[self._voltmeter_channel]

    @property
    def mca(self):
        return self.mcs.mcas[self._scaler_channel]

    async def connect(
        self,
        mock: bool | LazyMock = False,
        timeout: float = DEFAULT_TIMEOUT,
        force_reconnect: bool = False,
    ):
        """Connect self and all child Devices.

        Contains a timeout that gets propagated to child.connect methods.

        Parameters
        ----------
        mock:
            If True then use ``MockSignalBackend`` for all Signals
        timeout:
            Time to wait before failing with a TimeoutError.

        """
        await super().connect(
            mock=mock, timeout=timeout, force_reconnect=force_reconnect
        )
        # Update the device's name
        auto_name = bool(self.auto_name) or (self.auto_name is None and self.name == "")
        if bool(auto_name):
            try:
                desc = await self.scaler_channel.description.get_value()
            except Exception as exc:
                warnings.warn(
                    f"Could not read description for {self}. Name not updated. {exc}"
                )
                return
            # Only update the name if the description has been set
            if desc != "":
                self.set_name(desc)
                # Update the labjack's input's .DESC field to match the scaler channel
                await self.voltmeter_channel.description.set(desc)

    async def default_timeout(self) -> float:
        """Calculate the expected timeout for triggering this ion chamber.

        If ``self.mcs.scaler.preset_time`` is set and the first
        (clock) channel is serving as a gate
        (``self.mcs.scaler.channels[0].is_gate.get_value() == True``)
        then the timeout is a little longer than the preset
        time.

        Otherwise the timeout is calculated based on the longest time
        the scaler can count for based on when the channel 0 clock
        register would fill up. For example, a 32-bit scaler with a
        9.6 MHz external clock could count for up to:

          2**32 / 9600000 = 447.4 seconds

        Returns
        =======
        timeout
          The optimal timeout for trigger this ion chamber's scaler.

        """
        aws = [
            self.mcs.scaler.channels[0].is_gate.get_value(),
            self.mcs.scaler.preset_time.get_value(),
            self.mcs.scaler.clock_frequency.get_value(),
        ]
        is_time_limited, count_time, clock_freq = await asyncio.gather(*aws)
        if is_time_limited:
            # We're using the preset time to decide when to stop
            return count_time + DEFAULT_TIMEOUT
        else:
            # Use the maximum time the scaler could possibly count
            max_counts = 2**self._clock_register_width
            max_count_time = max_counts / clock_freq
            return max_count_time + DEFAULT_TIMEOUT

    @AsyncStatus.wrap
    async def trigger(self, record_dark_current=False):
        """Instruct the ion chamber's scaler to capture one data point.

        Parameters
        ==========
        record_dark_current
          If true, this measurement will be saved as the dark current
          reading.

        """
        # Make sure we have a fresh voltmeter reading
        await self.voltmeter_channel.trigger()
        # Recording the dark current is done differently
        if record_dark_current:
            await self.record_dark_current()
            return
        # Calculate expected timeout value
        timeout = await self.default_timeout()
        # Check if we've seen this signal before
        signal = self.mcs.scaler.count
        last_status = self._trigger_statuses.get(signal.source)
        # Previous trigger is still going, so wait for that instead
        if last_status is not None and not last_status.done:
            await last_status
            return
        # Nothing to wait on yet, so trigger the scaler and stash the result
        st = signal.set(True, timeout=timeout)
        self._trigger_statuses[signal.source] = st
        await st

    async def record_dark_current(self):
        signal = self.mcs.scaler.record_dark_current
        await signal.trigger(wait=False)
        # Now wait for the count state to return to done
        integration_time = await self.mcs.scaler.dark_current_time.get_value()
        timeout = integration_time + DEFAULT_TIMEOUT
        count_signal = self.mcs.scaler.count
        await wait_for_value(count_signal, False, timeout=timeout)

    def record_fly_reading(self, reading, **kwargs):
        if self._is_flying:
            self._fly_readings.append(reading)

    @AsyncStatus.wrap
    async def prepare(self, value: TriggerInfo):
        """Prepare the ion chamber for fly scanning."""
        self.start_timestamp = None
        # Set some configuration PVs on the MCS
        aws = [
            self.mcs.count_on_start.set(True),
            self.mcs.channel_advance_source.set(self.mcs.ChannelAdvanceSource.INTERNAL),
            self.mcs.num_channels.set(await self.mcs.num_channels_max.get_value()),
            self.mcs.erase_all.trigger(),
        ]
        if value.livetime is not None:
            aws += [self.mcs.dwell_time.set(value.livetime)]
        await asyncio.gather(*aws)
        # Start acquiring data
        self._fly_readings: list[dict] = []
        self._is_flying = False  # Gets set during kickoff

    @AsyncStatus.wrap
    async def kickoff(self):
        """Start recording data for the fly scan."""
        # Watch for new data being collected so we can save timestamps
        self.mcs.current_channel.subscribe(self.record_fly_reading)
        # Start acquiring
        self.mcs.start_all.trigger(wait=False)
        # Wait for acquisition to start
        await wait_for_value(
            self.mcs.acquiring, self.mcs.Acquiring.ACQUIRING, timeout=DEFAULT_TIMEOUT
        )
        self._is_flying = True
        return

    @AsyncStatus.wrap
    async def complete(self):
        """Finish detector fly-scan acquisition."""
        await self.mcs.stop_all.trigger()
        self._is_flying = False

    async def collect_pages(self):
        # Prepare the individual signal data-sets
        timestamps = [
            d[self.mcs.current_channel.name]["timestamp"] for d in self._fly_readings
        ]
        num_points = len(timestamps)
        raw_counts = (await self.mca.spectrum.get_value())[:num_points]
        raw_times = await self.mcs.mcas[0].spectrum.get_value()
        clock_freq = await self.mcs.scaler.clock_frequency.get_value()
        times = raw_times / clock_freq
        # Apply the dark current correction
        offset_rate = await self.scaler_channel.offset_rate.get_value()
        net_counts = raw_counts - offset_rate * times
        # Build the results dictionary to be sent out
        data = {
            self.scaler_channel.raw_count.name: raw_counts,
            self.scaler_channel.net_count.name: net_counts,
            self.mcs.scaler.elapsed_time.name: times,
        }
        results = {
            "time": max(timestamps),
            "data": data,
            "timestamps": {key: timestamps for key in data.keys()},
        }
        yield results

    async def describe_collect(self) -> Dict[str, Dict]:
        signals = [
            self.scaler_channel.raw_count,
            self.scaler_channel.net_count,
            self.mcs.scaler.elapsed_time,
        ]
        descriptions = await asyncio.gather(*(sig.describe() for sig in signals))
        desc = {k: v for desc in descriptions for k, v in desc.items()}
        return {self.name: desc}

    @property
    def default_time_signal(self):
        """The signal to use for setting exposure time when no other signal is
        provided.

        """
        return self.mcs.scaler.preset_time
