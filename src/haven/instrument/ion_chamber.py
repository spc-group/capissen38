"""Holds ion chamber detector descriptions and assignments to EPICS PVs."""

import asyncio
import logging
import math
import time
import warnings
from collections import OrderedDict
from typing import Dict, Generator

import numpy as np
import pint
from aioca import caget
from apstools.devices import SRS570_PreAmplifier
from ophyd import Component as Cpt
from ophyd import Device, EpicsSignal, EpicsSignalRO
from ophyd import FormattedComponent as FCpt
from ophyd import Kind, Signal, flyers, status
from ophyd.mca import EpicsMCARecord
from ophyd.ophydobj import OphydObject
from ophyd.signal import DerivedSignal, InternalSignal
from ophyd.status import SubscriptionStatus
from ophyd.utils.errors import OpException
from pcdsdevices.signal import MultiDerivedSignal, MultiDerivedSignalRO
from pcdsdevices.type_hints import OphydDataType, SignalToValue

from .. import exceptions
from .._iconfig import load_config
from .device import aload_devices, await_for_connection, make_device
from .instrument_registry import registry
from .labjack import AnalogInput
from .scaler_triggered import ScalerSignalRO, ScalerTriggered

log = logging.getLogger(__name__)


__all__ = ["IonChamber", "load_ion_chambers"]


class VoltageSignal(DerivedSignal):
    """Calculate the voltage at the output of the pre-amp."""

    max_volts: float = 10.0

    def inverse(self, value):
        """Calculate the voltage given a scaler count."""
        clock_ticks = self.parent.clock_ticks.get()
        if clock_ticks == 0:
            return 0
        return self.max_volts * value / clock_ticks


class CurrentSignal(DerivedSignal):
    """Calculate the current in amps at the input of the pre-amp."""

    def preamp(self):
        """Find which parent in the device hierarchy has the preamp."""
        device = self
        while device is not None:
            if isinstance(getattr(device, "preamp", None), IonChamberPreAmplifier):
                return device.preamp
            else:
                # Move up a step in the hierarchy
                device = device.parent
        # If we get here, there's no pre-amp
        raise AttributeError(f"No ancestor of {self} has a pre-amp.")

    def inverse(self, value):
        """Calculate the current given a output voltage."""
        volts = value
        preamp = self.preamp()
        gain = preamp.gain.get()
        offset_current = preamp.offset_current.get()
        return volts / gain - offset_current


class Voltmeter(AnalogInput):
    amps: OphydObject = Cpt(CurrentSignal, derived_from="volts", kind="normal")
    # Rename ``final_value`` to ``volts``
    final_value = None
    volts = Cpt(EpicsSignal, ".VAL", kind="normal")


class IonChamberPreAmplifier(SRS570_PreAmplifier):
    """An SRS-570 pre-amplifier driven by an ion chamber.

        Has extra signals for walking up and down the sensitivity
        range. *gain_level* is corresponds to the inverse of the
        combination of *sensitivity_value* and *sensitivity_unit*. Setting
        *gain_level* to 0 sets *sensitivity_value* and *sensitivity_unit*
        to "1 mA/V".

    By setting the *gain_level* signal, the offset is
        also set to be 10% of the sensitivity.

    """

    values = ["1", "2", "5", "10", "20", "50", "100", "200", "500"]
    units = ["pA/V", "nA/V", "uA/V", "mA/V"]
    offset_difference = -3  # How many levels higher should the offset be

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Reset the gain name, apstools converts "preamp_gain" to "preamp"
        self.gain.name += "_gain"
        # Subscriptions for updating the sensitivity text
        self.sensitivity_value.subscribe(self.update_sensitivity_text, run=False)
        self.sensitivity_unit.subscribe(self.update_sensitivity_text, run=True)

    def cb_gain(self, *args, **kwargs):
        """
        Called when sensitivity changes (EPICS CA monitor event).
        """
        gain = self.computed_gain()
        self.gain.put(gain, internal=True)
        self.gain_db.put(10 * math.log10(gain), internal=True)

    def computed_gain(self):
        """
        Amplifier gain (V/A), as floating-point number.
        """
        val = float(self.values[self.sensitivity_value.get()])
        amps = [
            1e-12,  # pA
            1e-9,  # nA
            1e-6,  # µA
            1e-3,  # mA
        ]
        multiplier = amps[self.sensitivity_unit.get()]
        inverse_gain = val * multiplier
        return 1 / inverse_gain

    def update_sensitivity_text(self, *args, obj: OphydObject, **kwargs):
        val = self.values[self.sensitivity_value.get()]
        unit = self.units[self.sensitivity_unit.get()]
        text = f"{val} {unit}"
        self.sensitivity_text.put(text, internal=True)

    def _level_to_value(self, level):
        return level % len(self.values)

    def _level_to_unit(self, level):
        return int(level / len(self.values))

    def _get_gain_level(self, mds: MultiDerivedSignal, items: SignalToValue) -> int:
        "Given a sensitivity value and unit, transform to the desired gain level."
        value = items[self.sensitivity_value]
        unit = items[self.sensitivity_unit]
        # Determine sensitivity level
        new_level = value + unit * len(self.values)
        # Convert to gain by inverting
        new_level = 27 - new_level
        log.debug(
            f"Getting sensitivity level {self.name}: {value} {unit} -> {new_level}"
        )
        return new_level

    def _put_gain_level(
        self, mds: MultiDerivedSignal, value: OphydDataType
    ) -> SignalToValue:
        "Given a gain level, transform to the desired sensitivity value and unit."
        # Determine new values
        new_level = 27 - value
        new_offset = max(new_level + self.offset_difference, 0)
        # Check for out of bounds
        lmin, lmax = (0, 27)
        msg = (
            f"Cannot set {self.name} outside range ({lmin}, {lmax}), received"
            f" {new_level}."
        )
        if new_level < lmin:
            raise exceptions.GainOverflow(msg)
        elif new_level > lmax:
            raise exceptions.GainOverflow(msg)
        # Return calculated gain and offset
        offset_value = self.values[self._level_to_value(new_offset)]
        offset_unit = self.units[self._level_to_unit(new_offset)].split("/")[0]
        result = OrderedDict()
        result.update({self.sensitivity_unit: self._level_to_unit(new_level)})
        result.update({self.sensitivity_value: self._level_to_value(new_level)})
        result.update({self.offset_value: offset_value})
        result.update({self.offset_unit: offset_unit})
        #     # set_all=1,
        # }
        return result

    def _get_offset_current(
        self, *, mds: MultiDerivedSignal, items: SignalToValue
    ) -> float:
        """Calculate the current in amps added to the signal before amplification."""
        if items[self.offset_on] in ["OFF", "0", 0]:
            return 0
        # Calculate offset current
        val = items[self.offset_value]
        sign = items[self.offset_sign]
        unit = items[self.offset_unit]
        try:
            val = float(f"{sign}{val}")
            current = pint.Quantity(float(val), unit).to("A").magnitude
        except ValueError:
            return 0
        return current

    # It's easier to calculate gains by enum index, so override the apstools signals
    sensitivity_value = Cpt(EpicsSignal, "sens_num", kind="config", string=False)
    sensitivity_unit = Cpt(EpicsSignal, "sens_unit", kind="config", string=False)

    gain_level = Cpt(
        MultiDerivedSignal,
        attrs=["sensitivity_value", "sensitivity_unit", "offset_value", "offset_unit"],
        calculate_on_get=_get_gain_level,
        calculate_on_put=_put_gain_level,
        kind=Kind.omitted,
    )
    offset_current = Cpt(
        MultiDerivedSignalRO,
        attrs=["offset_value", "offset_unit", "offset_on", "offset_sign"],
        calculate_on_get=_get_offset_current,
        kind=Kind.config,
    )

    # A text description of the what the current sensitivity settings are
    sensitivity_text = Cpt(
        InternalSignal,
        kind=Kind.config,
    )
    # Gain, but measured in various forms
    gain = Cpt(InternalSignal, name="gainerificf", kind="normal", value=1)
    gain_db = Cpt(InternalSignal, kind=Kind.config, value=0)


class IonChamber(ScalerTriggered, Device, flyers.FlyerInterface):
    """An ion chamber at a spectroscopy beamline.

    Also includes the pre-amplifier as ``.pre_amp``.

    This class also implements the bluesky/ophyd flyer
    interface. During *kickoff()*, previous data are erased and
    acquisition is started as a multi-channel scaler. It also watches
    for changes in the number of data collected and collects
    timestamps each time a new datum is captured. *complete()* stops
    acquisition. These timestamps, along with the measured data, are
    generated during *collect()*.

    Parameters
    ==========
    prefix
      The PV prefix of the overall scaler.
    ch_num
      The number (1-index) of the channel on the scaler. 1 is the
      timer, so your channel number should start at 2.
    name
      The bluesky-compatible name for this device.
    preamp_prefix
      The process variable prefix to the pre-amp that controls this
      ion chamber (e.g. "25idc:SR01").
    scaler_prefix
      The process variable prefix for the scaler that measures this
      ion chamber.
    voltmeter_prefix
      The process variable prefix for the voltmeter. This might be an
      analog input for a labjack, in which case try something like
      "LabJackT7_1:Ai0".

    Attributes
    ==========
    ch_num
      The channel number on the scaler, starting at 2 (1 is the timer).
    count
      The trigger to count scaler pulses.
    counts
      The counts coming from the scaler without any correction.
    volts
      The volts produced by the pre-amp, calculated from scaler
      counts.
    amps
      The current produced by the ion chamber, calculated from scaler
      counts and preamp settings.
    exposure_time
      Positioner for setting the count time on the scaler.
    preamp
      The SR570 pre-amplifier driving the signal.

    """

    stream_name: str = "primary"
    ch_num: int = 0
    ch_char: str
    start_timestamp: float = None
    count: OphydObject = FCpt(
        EpicsSignal, "{scaler_prefix}:scaler1.CNT", trigger_value=1, kind=Kind.omitted
    )
    description: OphydObject = FCpt(
        EpicsSignal, "{scaler_prefix}:scaler1.NM{ch_num}", kind=Kind.config
    )
    # Signal chain devices
    preamp = FCpt(IonChamberPreAmplifier, "{preamp_prefix}")
    voltmeter = FCpt(Voltmeter, "{voltmeter_prefix}", kind=Kind.hinted)
    # Measurement signals
    volts: OphydObject = Cpt(VoltageSignal, derived_from="counts", kind=Kind.normal)
    amps: OphydObject = Cpt(CurrentSignal, derived_from="volts", kind=Kind.hinted)
    counts: OphydObject = FCpt(
        EpicsSignalRO,
        "{scaler_prefix}:scaler1.S{ch_num}",
        kind=Kind.normal,
        auto_monitor=False,
    )
    gate: OphydObject = FCpt(
        EpicsSignal,
        "{scaler_prefix}:scaler1.G{ch_num}",
        kind=Kind.config,
    )
    preset_count: OphydObject = FCpt(
        EpicsSignal, "{scaler_prefix}:scaler1.PR{ch_num}", kind=Kind.config
    )
    frequency: OphydObject = FCpt(
        EpicsSignal,
        "{scaler_prefix}:scaler1.FREQ",
        kind=Kind.config,
    )
    clock_ticks: OphydObject = FCpt(
        EpicsSignalRO,
        "{scaler_prefix}:scaler1.S1",
        kind=Kind.normal,
    )
    # Old Scaler mode support
    offset: OphydObject = FCpt(
        ScalerSignalRO, "{scaler_prefix}:scaler1_{offset_suffix}", kind=Kind.config
    )
    net_counts: OphydObject = FCpt(
        ScalerSignalRO, "{scaler_prefix}:scaler1_netA.{ch_char}", kind=Kind.hinted
    )
    exposure_time: OphydObject = FCpt(
        EpicsSignal, "{scaler_prefix}:scaler1.TP", kind=Kind.normal
    )
    auto_count: OphydObject = FCpt(
        EpicsSignal, "{scaler_prefix}:scaler1.CONT", kind=Kind.omitted
    )
    record_dark_current: OphydObject = FCpt(
        EpicsSignal, "{scaler_prefix}:scaler1_offset_start.PROC", kind=Kind.omitted
    )
    record_dark_time: OphydObject = FCpt(
        EpicsSignal, "{scaler_prefix}:scaler1_offset_time.VAL", kind=Kind.config
    )
    # Multi-channel scaler support
    start_all: OphydObject = FCpt(
        EpicsSignal, "{scaler_prefix}:StartAll", kind=Kind.omitted
    )
    stop_all: OphydObject = FCpt(
        EpicsSignal, "{scaler_prefix}:StopAll", kind=Kind.omitted
    )
    erase_all: OphydObject = FCpt(
        EpicsSignal, "{scaler_prefix}:EraseAll", kind=Kind.omitted
    )
    erase_start: OphydObject = FCpt(
        EpicsSignal,
        "{scaler_prefix}:EraseStart",
        kind=Kind.omitted,
    )
    acquiring: OphydObject = FCpt(
        EpicsSignal, "{scaler_prefix}:Acquiring", kind=Kind.omitted
    )
    channel_advance_source: OphydObject = FCpt(
        EpicsSignal,
        "{scaler_prefix}:ChannelAdvance",
        kind=Kind.config,
    )
    num_channels_to_use: OphydObject = FCpt(
        EpicsSignal,
        "{scaler_prefix}:NuseAll",
        kind=Kind.config,
    )
    max_channels: OphydObject = FCpt(
        EpicsSignal, "{scaler_prefix}:MaxChannels", kind=Kind.config
    )
    current_channel: OphydObject = FCpt(
        EpicsSignal,
        "{scaler_prefix}:CurrentChannel",
        kind=Kind.normal,
    )
    channel_one_source: OphydObject = FCpt(
        EpicsSignal, "{scaler_prefix}:Channel1Source", kind=Kind.config
    )
    count_on_start: OphydObject = FCpt(
        EpicsSignal, "{scaler_prefix}:CountOnStart", kind=Kind.config
    )
    mca: OphydObject = FCpt(
        EpicsMCARecord, "{scaler_prefix}:mca{ch_num}", kind=Kind.omitted
    )
    mca_times: OphydObject = FCpt(
        EpicsMCARecord, "{scaler_prefix}:mca1", kind=Kind.omitted
    )

    # Virtual signals to handle fly-scanning
    timestamps: list = []
    num_bins = Cpt(Signal)

    _default_read_attrs = [
        "counts",
        "volts",
        "exposure_time",
        "net_counts",
        "voltmeter",
    ]

    def __init__(
        self,
        prefix: str,
        ch_num: int,
        name: str,
        preamp_prefix: str = None,
        scaler_prefix: str = None,
        voltmeter_prefix: str = None,
        *args,
        **kwargs,
    ):
        # Set up the channel number for this scaler channel
        if ch_num < 1:
            raise ValueError(f"Scaler channels must be greater than 0: {ch_num}")
        self.ch_num = ch_num
        self.ch_char = self.num_to_char(ch_num)
        # Determine which prefix to use for the scaler
        if scaler_prefix is None:
            scaler_prefix = prefix
        self.scaler_prefix = scaler_prefix
        # Save an epics path to the preamp
        if preamp_prefix is None:
            preamp_prefix = prefix
        self.preamp_prefix = preamp_prefix
        # Save an epics path for the voltmeter (nominally a labjack)
        self.voltmeter_prefix = voltmeter_prefix
        # Determine the offset PV since it follows weird numbering conventions
        calc_num = int((self.ch_num - 1) / 4)
        calc_char = self.num_to_char(((self.ch_num - 1) % 4) + 1)
        self.offset_suffix = f"offset{calc_num}.{calc_char}"
        # Initialize all the other Device stuff
        super().__init__(prefix=prefix, name=name, *args, **kwargs)
        # Set signal values to stage
        self.stage_sigs[self.auto_count] = 0
        # Sync the ion chamber description with the voltmeter description
        self.description.subscribe(self.update_voltmeter_description, run=True)

    def update_voltmeter_description(self, *args, value, **kwargs):
        self.voltmeter.description.put(value)

    def num_to_char(self, num):
        char = chr(64 + num)
        return char

    def change_sensitivity(self, step: int) -> status.StatusBase:
        """Change the gain on the pre-amp by the given number of steps.

        Parameters
        ==========
        step
          How many levels to change the sensitivity. Positive numbers
          increase the gain, negative numbers decrease the gain.

        Returns
        =======
        status.StatusBase
          The status that will be marked complete once the sensitivity
          is changed.

        """
        new_sens_level = self.sensitivity.sens_level.readback.get() + step
        try:
            status = self.sensitivity.sens_level.set(new_sens_level)
        except ValueError as e:
            raise exceptions.GainOverflow(f"{self.name} -> {e}")
        return status

    def increase_gain(self) -> status.StatusBase:
        """Increase the gain (descrease the sensitivity) of the ion chamber's
        pre-amp.

        Returns
        =======
        status.StatusBase
          Ophyd status object for the value and gain of the
          sensitivity in the pre-amp.

        """
        return self.change_sensitivity(-1)

    def decrease_gain(self) -> status.StatusBase:
        """Decrease the gain (increase the sensitivity) of the ion chamber's
        pre-amp.

        Returns
        =======
        status.StatusBase
          Ophyd status object for the value and gain of the
          sensitivity in the pre-amp.

        """
        return self.change_sensitivity(1)

    def record_timestamp(self, *, old_value, value, timestamp, **kwargs):
        self.timestamps.append(timestamp)

    def kickoff(self) -> status.StatusBase:
        def check_acquiring(*, old_value, value, **kwargs):
            is_acquiring = bool(value)
            if is_acquiring:
                self.start_timestamp = time.time()
            return is_acquiring

        self.start_timestamp = None
        # Set some configuration PVs on the MCS
        self.count_on_start.set(1).wait()
        # Start acquiring data
        self.erase_start.set(1).wait()
        # Wait for the "Acquiring" to start
        status = SubscriptionStatus(self.acquiring, check_acquiring)
        # Watch for new data being collected so we can save timestamps
        self.timestamps = []
        self.current_channel.subscribe(self.record_timestamp)
        return status

    def complete(self) -> status.StatusBase:
        status = self.stop_all.set(1, settle_time=0.05)
        return status

    def collect(self) -> Generator[Dict, None, None]:
        net_counts_name = self.net_counts.name
        # Use the scaler's clock counter to calculate timestamps
        times = self.mca_times.spectrum.get()
        times = np.divide(times, self.frequency.get(), casting="safe")
        times = np.cumsum(times)
        pso_timestamps = times + self.start_timestamp
        # Retrieve data, except for first point (during taxiing)
        data = self.mca.spectrum.get()[1:]
        # Convert timestamps from PSO pulses to pixels
        pixel_timestamps = (pso_timestamps[1:] + pso_timestamps[:-1]) / 2
        # Create data events
        for ts, value in zip(pixel_timestamps, data):
            yield {
                "data": {net_counts_name: value},
                "timestamps": {net_counts_name: ts},
                "time": ts,
            }

    def describe_collect(self) -> Dict[str, Dict]:
        """Describe details for the flyer collect() method"""
        desc = OrderedDict()
        desc.update(self.net_counts.describe())
        return {self.name: desc}


async def make_ion_chamber_device(
    prefix: str, ch_num: int, name: str, preamp_prefix: str
):
    ic = IonChamber(
        prefix=prefix,
        ch_num=ch_num,
        name=name,
        preamp_prefix=preamp_prefix,
        labels={"ion_chambers"},
    )
    try:
        await await_for_connection(ic)
    except TimeoutError as exc:
        raise
        log.warning(
            f"Could not connect to ion chamber: {name} ({prefix}, {preamp_prefix})"
        )
    else:
        log.info(f"Created ion chamber: {name} ({prefix}, {preamp_prefix})")
        return ic


async def load_ion_chamber(
    preamp_prefix: str, scaler_prefix: str, voltmeter_prefix: str, ch_num: int
):
    """Create an IonChamber ophyd device.

    When autoloading the ion chambers from the config file, this
    function will parse the config file arguments and convert them
    into the forms needed for the IonChamber device itself.

    """
    # Determine ion_chamber configuration
    preamp_prefix = f"{preamp_prefix}:SR{ch_num:02}:"
    desc_pv = f"{scaler_prefix}:scaler1.NM{ch_num}"
    # Determine which labjack channel is measuring the voltmeter
    ic_idx = ch_num - 2
    # 5 pre-amps per labjack
    lj_num = int(ic_idx / 5)
    # Only use even labjack channels since it's a differential signal
    lj_chan = ic_idx % 5
    # Only use this ion chamber if it has a name
    try:
        name = await caget(desc_pv)
    except asyncio.exceptions.TimeoutError:
        # Scaler channel is unreachable, so skip it
        log.warning(f"Could not connect to ion_chamber: {desc_pv}")
        return
    if name == "":
        log.info(f"Skipping unnamed ion chamber: {desc_pv}")
        return
    # Create the ion chamber device
    ion_chamber = await make_device(
        IonChamber,
        prefix=scaler_prefix,
        ch_num=ch_num,
        name=name,
        preamp_prefix=preamp_prefix,
        voltmeter_prefix=f"{voltmeter_prefix}{lj_num}:Ai{lj_chan}",
        labels={"ion_chambers"},
    )
    # Ensure the voltmeter is in single-ended mode to measure pre-amp
    if hasattr(ion_chamber, "voltmeter"):
        try:
            ion_chamber.voltmeter.differential.set(0).wait(timeout=1)
        except OpException as exc:
            msg = (
                f"Could not set voltmeter {ion_chamber.name} channel to single-ended mode:"
                f" {exc}"
            )
            log.warning(msg)
            warnings.warn(msg)
    return ion_chamber


def load_ion_chamber_coros(config=None):
    # Load IOC prefixes from the config file
    if config is None:
        config = load_config()
    # vme_ioc = config["ion_chamber"]["scaler"]["ioc"]
    # scaler_record = config["ion_chamber"]["scaler"]["record"]
    scaler_prefix = config["ion_chamber"]["scaler"]["prefix"]
    preamp_prefix = config["ion_chamber"]["preamp"]["prefix"]
    voltmeter_prefix = config["ion_chamber"]["voltmeter"]["prefix"]
    ion_chambers = []
    # Loop through the configuration sections and create ion chambers co-routines
    for ch_num in config["ion_chamber"]["scaler"]["channels"]:
        yield load_ion_chamber(
            preamp_prefix=preamp_prefix,
            scaler_prefix=scaler_prefix,
            ch_num=ch_num,
            voltmeter_prefix=voltmeter_prefix,
        )


def load_ion_chambers(config=None):
    return asyncio.run(aload_devices(*load_ion_chamber_coros(config=config)))


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
