"""
Ophyd support for Stanford Research Systems 570 preamplifier from synApps

Public Structures

This device connects with the SRS570 support from synApps.
(https://github.com/epics-modules/ip/blob/master/ipApp/Db/SR570.db)

The SRS570 synApps support is part of the ``ip`` module:
https://htmlpreview.github.io/?https://raw.githubusercontent.com/epics-modules/ip/R3-6-1/documentation/swaitRecord.html

:see: https://github.com/epics-modules/ip
"""

import asyncio
import logging
import math
from collections import OrderedDict
from typing import Optional, Type

from ophyd_async.core import (
    CALCULATE_TIMEOUT,
    AsyncStatus,
    CalculatableTimeout,
    Device,
    SignalRW,
    StrictEnum,
    T,
)
from ophyd_async.epics.core import epics_signal_rw, epics_signal_x
from ophyd_async.epics.core._signal import _epics_signal_backend

from .. import exceptions
from .signal import derived_signal_r, derived_signal_rw

logger = logging.getLogger(__name__)


gain_units = ["pA/V", "nA/V", "uA/V", "mA/V"]
gain_values = ["1", "2", "5", "10", "20", "50", "100", "200", "500"]
gain_modes = ["LOW NOISE", "HIGH BW"]


class Sign(StrictEnum):
    PLUS = "+"
    MINUS = "-"


class Cal(StrictEnum):
    CAL = "CAL"
    UNCAL = "UNCAL"


# Settling times measured from the 25-ID-C upstream I0 chamber's SR-570
# (sensitivity_value, sensitivity_unit, gain_mode): settle_time
settling_times = {
    # pA/V
    ("1", "pA/V", "HIGH BW"): 2.5,
    ("2", "pA/V", "HIGH BW"): 2,
    ("5", "pA/V", "HIGH BW"): 2.0,
    ("10", "pA/V", "HIGH BW"): 0.5,
    ("20", "pA/V", "HIGH BW"): 0.5,
    ("50", "pA/V", "HIGH BW"): 0.5,
    ("100", "pA/V", "HIGH BW"): 0.5,
    ("200", "pA/V", "HIGH BW"): 0.5,
    ("500", "pA/V", "HIGH BW"): 0.5,
    ("1", "pA/V", "LOW NOISE"): 3.0,
    ("2", "pA/V", "LOW NOISE"): 2.5,
    ("5", "pA/V", "LOW NOISE"): 2.0,
    ("10", "pA/V", "LOW NOISE"): 2.0,
    ("20", "pA/V", "LOW NOISE"): 1.75,
    ("50", "pA/V", "LOW NOISE"): 1.5,
    ("100", "pA/V", "LOW NOISE"): 1.25,
    ("200", "pA/V", "LOW NOISE"): 0.5,
    ("500", "pA/V", "LOW NOISE"): 0.5,
}
settling_times.update(
    {
        # nA/V, high bandwidth
        (gain_values[idx], "nA/V", "HIGH BW"): 0.5
        for idx in range(9)
    }
)
settling_times.update(
    {
        # nA/V, low noise
        (gain_values[idx], "nA/V", "LOW NOISE"): 0.5
        for idx in range(9)
    }
)
settling_times.update(
    {
        # μA/V, high bandwidth
        (gain_values[idx], "uA/V", "HIGH BW"): 0.5
        for idx in range(9)
    }
)
settling_times.update(
    {
        # μA/V, low noise
        (gain_values[idx], "uA/V", "LOW NOISE"): 0.5
        for idx in range(9)
    }
)
settling_times.update(
    {
        ("1", "mA/V", "HIGH BW"): 0.5,
        ("1", "mA/V", "LOW NOISE"): 0.5,
    }
)


def calculate_settle_time(gain_value: int, gain_unit: int, gain_mode: str):
    """Determine the best settle time for a given combination of parameters.

    Parameters can be strings of indexes.

    """
    # Convert indexes to string values
    try:
        new_value = gain_values[gain_value]
    except (TypeError, IndexError):
        pass
    try:
        new_unit = gain_units[gain_unit]
    except (TypeError, IndexError):
        pass
    try:
        new_mode = gain_modes[gain_mode]
    except (TypeError, IndexError):
        pass
    # Get calibrated settle time, or None to use the Ophyd default
    return settling_times.get((new_value, new_unit, new_mode))


class GainSignal(SignalRW):
    async def calculate_settle_time(self, value):
        signals = [
            self.parent.sensitivity_value,
            self.parent.sensitivity_unit,
            self.parent.gain_mode,
        ]
        args = [value if self is sig else (await sig.get_value()) for sig in signals]
        val, unit, mode = args
        # Resolve string values to indices if provided
        if val in gain_values:
            val = gain_values.index(val)
        if unit in gain_units:
            unit = gain_units.index(unit)
        if mode in gain_modes:
            mode = gain_modes.index(mode)
        # Low-drift mode uses the same settling times as low-noise mode
        if mode == "LOW DRIFT":
            mode = "LOW NOISE"
        # Calculate settling time
        return calculate_settle_time(gain_value=val, gain_unit=unit, gain_mode=mode)

    @AsyncStatus.wrap
    async def set(
        self, value: T, wait=True, timeout: CalculatableTimeout = CALCULATE_TIMEOUT
    ):
        aw = super().set(value=value, wait=wait, timeout=timeout)
        if wait:
            await aw
            settle_time = await self.calculate_settle_time(value)
            await asyncio.sleep(settle_time)


def gain_signal(
    datatype: Type[T], read_pv: str, write_pv: Optional[str] = None, name: str = ""
) -> SignalRW[T]:
    """Create a `SignalRW` for changing gain and waiting for settling time.

    The gain signals are not ready to use immediately due to the amp's
    innate RC relaxation.

    Parameters
    ----------
    datatype:
        Check that the PV is of this type
    read_pv:
        The PV to read and monitor
    write_pv:
        If given, use this PV to write to, otherwise use read_pv

    """
    backend = _epics_signal_backend(datatype, read_pv, write_pv or read_pv)
    return GainSignal(backend, name=name)


class SRS570PreAmplifier(Device):
    """Ophyd-async support for Stanford Research Systems 570 preamp."""

    offset_difference = -3  # How many levels higher should the offset be

    class FilterType(StrictEnum):
        NO_FILTER = "  No filter"
        _6DB_HIGHPASS = " 6 dB highpass"
        _12DB_HIGHPASS = "12 dB highpass"
        _6DB_BANDPASS = " 6 dB bandpass"
        _6DB_LOWPASS = " 6 dB lowpass"
        _12DB_LOWPASS = "12 dB lowpass"

    class FilterLowPass(StrictEnum):
        _0_03_HZ = "  0.03 Hz"
        _0_1_HZ = "  0.1 Hz"
        _0_3_HZ = "  0.3 Hz"
        _1_HZ = "  1   Hz"
        _3_HZ = "  3   Hz"
        _10_HZ = " 10   Hz"
        _30_HZ = " 30   Hz"
        _100_HZ = "100   Hz"
        _300_HZ = "300   Hz"
        _1_KHZ = "  1   kHz"
        _3_KHZ = "  3   kHz"
        _10_KHZ = " 10   kHz"
        _30_KHZ = " 30   kHz"
        _100_KHZ = "100   kHz"
        _300_KHZ = "300   kHz"
        _1_MHZ = "  1   MHz"

    class FilterHighPass(StrictEnum):
        _0_03_HZ = "  0.03 Hz"
        _0_1_HZ = "  0.1 Hz"
        _0_3_HZ = "  0.3 Hz"
        _1_HZ = "  1   Hz"
        _3_HZ = "  3   Hz"
        _10_HZ = " 10   Hz"
        _30_HZ = " 30   Hz"
        _100_HZ = "100   Hz"
        _300_HZ = "300   Hz"
        _1_KHZ = "  1   kHz"
        _3_KHZ = "  3   kHz"
        _10_KHZ = " 10   kHz"

    class GainMode(StrictEnum):
        LOW_NOISE = "LOW NOISE"
        HIGH_BW = "HIGH BW"
        LOW_DRIFT = "LOW DRIFT"

    class SensValue(StrictEnum):
        ONE = "1"
        TWO = "2"
        FIVE = "5"
        TEN = "10"
        TWENTY = "20"
        FIFTY = "50"
        ONE_HUNDRED = "100"
        TWO_HUNDRED = "200"
        FIVE_HUNDRED = "500"

    class SensUnit(StrictEnum):
        PICOAMP_PER_VOLT = "pA/V"
        NANOAMP_PER_VOLT = "nA/V"
        MICROAMP_PER_VOLT = "uA/V"
        MILLIAMP_PER_VOLT = "mA/V"

    class OffsetUnit(StrictEnum):
        PICOAMP = "pA"
        NANOAMP = "nA"
        MICROAMP = "uA"
        MILLIAMP = "mA"

    def __init__(self, prefix: str, name: str = ""):
        """
        Update the gain when the sensitivity changes.
        """
        self.sensitivity_value = gain_signal(self.SensValue, f"{prefix}sens_num")
        self.sensitivity_unit = gain_signal(self.SensUnit, f"{prefix}sens_unit")

        self.offset_on = epics_signal_rw(bool, f"{prefix}offset_on")
        self.offset_sign = epics_signal_rw(Sign, f"{prefix}offset_sign")
        self.offset_value = epics_signal_rw(self.SensValue, f"{prefix}offset_num")
        self.offset_unit = epics_signal_rw(self.OffsetUnit, f"{prefix}offset_unit")
        self.offset_fine = epics_signal_rw(int, f"{prefix}off_u_put")
        self.offset_cal = epics_signal_rw(Cal, f"{prefix}offset_cal")

        self.set_all = epics_signal_x(f"{prefix}init.PROC")

        self.bias_value = epics_signal_rw(int, f"{prefix}bias_put")
        self.bias_on = epics_signal_rw(bool, f"{prefix}bias_on")

        self.filter_type = epics_signal_rw(
            self.FilterType,
            f"{prefix}filter_type",
        )
        self.filter_reset = epics_signal_x(f"{prefix}filter_reset.PROC")
        self.filter_lowpass = epics_signal_rw(self.FilterLowPass, f"{prefix}low_freq")
        self.filter_highpass = epics_signal_rw(
            self.FilterHighPass, f"{prefix}high_freq"
        )
        self.gain_mode = gain_signal(self.GainMode, f"{prefix}gain_mode")
        self.invert = epics_signal_rw(bool, f"{prefix}invert_on")
        self.blank = epics_signal_rw(bool, f"{prefix}blank_on")

        # Gain signals derived from the sensitivity signals
        sens_signals = {
            "sens_value": self.sensitivity_value,
            "sens_unit": self.sensitivity_unit,
        }
        self.gain = derived_signal_r(
            float,
            derived_from=sens_signals,
            inverse=self._gain_from_sensitivity,
            units="V A⁻",
        )
        self.gain_db = derived_signal_r(
            float, derived_from={"gain": self.gain}, inverse=self._dB, units="dB"
        )
        level_signals = dict(
            offset_value=self.offset_value, offset_unit=self.offset_unit, **sens_signals
        )
        self.gain_level = derived_signal_rw(
            int,
            derived_from=level_signals,
            forward=self._from_gain_level,
            inverse=self._to_gain_level,
        )
        super().__init__(name=name)

    def _gain_from_sensitivity(self, values, *, sens_value, sens_unit):
        """
        Amplifier gain (V/A), as floating-point number.
        """
        # Convert the sensitivity to a proper number
        val = float(values[sens_value])
        # Determine multiplier based on the gain unit
        amps = {
            "pA": 1e-12,
            "nA": 1e-9,
            "uA": 1e-6,
            "mA": 1e-3,
        }
        multiplier = amps[values[sens_unit].split("/")[0]]
        inverse_gain = val * multiplier
        return 1 / inverse_gain

    def _dB(self, values, *, gain):
        """Convert a gain to be in decibels."""
        try:
            return 10 * math.log10(values[gain])
        except ValueError:
            return float("nan")

    async def _from_gain_level(
        self, value, *, sens_value, sens_unit, offset_value, offset_unit
    ):
        """Compute the sensitivity settings for a given level of gain."""
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
        result = OrderedDict()
        result[sens_unit] = self._level_to_unit(new_level)
        result[sens_value] = self._level_to_value(new_level)
        result[offset_value] = self._level_to_value(new_offset)
        result[offset_unit] = self._level_to_unit(new_offset).split("/")[0]
        return result

    def _level_to_value(self, level):
        """Convert a gain index level to its string value."""
        values = [v.value for v in self.SensValue]
        return values[int(level) % len(values)]

    def _level_to_unit(self, level):
        """Convert a gain index level to its string unit."""
        units = [u.value for u in self.SensUnit]
        values = [v.value for v in self.SensValue]
        return units[int(level / len(values))]

    def _sensitivity_to_level(self, value: str, unit: str) -> int:
        """Convert a gain value and unit to its level index."""
        values = [v.value for v in self.SensValue]
        units = [u.value for u in self.SensUnit]
        value_idx = values.index(value)
        unit_idx = units.index(unit)
        # Determine sensitivity level
        new_level = value_idx + unit_idx * len(values)
        # Convert to gain by inverting
        new_level = 27 - new_level
        return new_level

    def _to_gain_level(
        self, values, *, sens_value, sens_unit, offset_value=None, offset_unit=None
    ):
        """Compute the level of gain for given sensitivity settings."""
        # from pprint import pprint
        # pprint(values)
        return self._sensitivity_to_level(values[sens_value], values[sens_unit])


# -----------------------------------------------------------------------------
# :author:    Mark Wolfman
# :email:     wolfman@anl.gov
# :copyright: Copyright © 2024, UChicago Argonne, LLC
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
