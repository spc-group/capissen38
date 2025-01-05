"""Ophyd device support for a set of XIA PFCU-controlled filters.

A PFCUFilterBank controls a set of 4 filters. Optionally, 2 filters in
a filter bank can be used as a shutter.

"""

import logging
from enum import IntEnum
from typing import Sequence

from ophyd_async.core import (
    DeviceVector,
    StandardReadable,
    StrictEnum,
    SubsetEnum,
    soft_signal_rw,
)
from ophyd_async.epics.core import epics_signal_r, epics_signal_rw

from haven.devices.shutter import ShutterState
from haven.devices.signal import derived_signal_r, derived_signal_rw
from haven.positioner import Positioner

__all__ = ["PFCUFilterBank", "PFCUFilter", "PFCUShutter"]

log = logging.getLogger(__name__)


class ConfigBits(StrictEnum):
    ZERO = "0000"
    ONE = "0001"
    TWO = "0010"
    THREE = "0011"
    FOUR = "0100"
    FIVE = "0101"
    SIX = "0110"
    SEVEN = "0111"
    EIGHT = "1000"
    NINE = "1001"
    TEN = "1010"
    ELEVEN = "1011"
    TWELVE = "1100"
    THIRTEEN = "1101"
    FOURTEEN = "1110"
    FIFTEEN = "1111"


class FilterPosition(SubsetEnum):
    OUT = "Out"
    IN = "In"
    SHORT_CIRCUIT = "Short Circuit"
    OPEN_CIRCUIT = "Open Circuit"


class FilterState(IntEnum):
    OUT = 0  # 0b000
    IN = 1  # 0b001
    FAULT = 3  # 0b011
    UNKNOWN = 4  # 0b100


class Material(SubsetEnum):
    ALUMINUM = "Al"
    MOLYBDENUM = "Mo"
    TITANIUM = "Ti"
    GLASS = "Glass"
    OTHER = "Other"


def normalize_readback(values, readback):
    return {
        FilterPosition.OUT: FilterState.OUT,
        FilterPosition.IN: FilterState.IN,
        FilterPosition.SHORT_CIRCUIT: FilterState.FAULT,
        FilterPosition.OPEN_CIRCUIT: FilterState.FAULT,
    }.get(values[readback], FilterState.UNKNOWN)


class PFCUFilter(Positioner):
    """A single filter in a PFCU filter bank.

    E.g. 25idc:pfcu0:filter1_mat
    """

    _ophyd_labels_ = {"filters"}

    def __init__(self, prefix: str, *, name: str = ""):
        with self.add_children_as_readables("config"):
            self.material = epics_signal_rw(Material, f"{prefix}_mat")
            self.thick = epics_signal_rw(float, f"{prefix}_thick")
            self.thick_unit = epics_signal_rw(str, f"{prefix}_thick.EGU")
            self.notes = epics_signal_rw(str, f"{prefix}_other")
        # We need a second "private" readback to standardize the types
        self._readback = epics_signal_r(FilterPosition, f"{prefix}_RBV")
        with self.add_children_as_readables():
            self.readback = derived_signal_r(
                int,
                derived_from={"readback": self._readback},
                inverse=normalize_readback,
            )
        self.setpoint = epics_signal_rw(bool, prefix)
        # Just use convenient values for positioner signals since there's no real position
        self.velocity = soft_signal_rw(float, initial_value=0.5)
        self.units = soft_signal_rw(str, initial_value="")
        self.precision = soft_signal_rw(int, initial_value=0)
        super().__init__(name=name)


shutter_state_map = {
    # (top filter, bottom filter): state
    (ShutterState.OPEN, ShutterState.CLOSED): ShutterState.OPEN,
    (ShutterState.CLOSED, ShutterState.OPEN): ShutterState.CLOSED,
    (ShutterState.OPEN, ShutterState.OPEN): ShutterState.FAULT,
    (ShutterState.CLOSED, ShutterState.CLOSED): ShutterState.FAULT,
}


class PFCUFilterBank(StandardReadable):
    """A XIA PFCU4 bank of four filters and/or shutters.

    Filters are indexed from 0, even though the EPICS support indexes
    from 1.

    Parameters
    ==========
    shutters
      Sets of filter numbers to use as shutters. Each entry in
      *shutters* should be a tuple like (top, bottom) where the first
      filter (top) is open when the filter is set to "out".

    """

    num_slots: int

    def __init__(
        self,
        prefix: str,
        *,
        name: str = "",
        num_slots: int = 4,
        shutters: Sequence[tuple[int, int]] = [],
    ):
        all_shutters = [v for shutter in shutters for v in shutter]
        is_in_bounds = [0 < shtr < num_slots for shtr in all_shutters]
        if not all(is_in_bounds):
            raise ValueError(
                f"Shutter indices {shutters} for filterbank {name=} must be in the range (0, {num_slots})."
            )
        self.num_slots = num_slots
        # Positioner signals
        self.setpoint = epics_signal_rw(ConfigBits, f"{prefix}config")
        with self.add_children_as_readables():
            self.readback = epics_signal_r(ConfigBits, f"{prefix}config_RBV")
        # Sort out filters vs shutters
        filters = [idx for idx in range(num_slots) if idx not in all_shutters]
        with self.add_children_as_readables():
            # Create shutters
            self.shutters = DeviceVector(
                {
                    idx: PFCUShutter(
                        prefix=prefix,
                        top_filter=top,
                        bottom_filter=btm,
                        filter_bank=self,
                    )
                    for idx, (top, btm) in enumerate(shutters)
                }
            )
            # Create filters
            self.filters = DeviceVector(
                {idx: PFCUFilter(prefix=f"{prefix}filter{idx+1}") for idx in filters}
            )
        super().__init__(name=name)


class PFCUShutter(Positioner):
    """A shutter made of two PFCU4 filters.

    For faster operation, both filters will be moved at the same
    time. That means this shutter must be a sub-component of a
    :py:class:`PFCUFilterBank`.

    Parameters
    ==========
    top_filter
      The index of the filter that is open when the filter is set to
      "out".
    bottom_filter
      The index of the filter that is open when the filter is set to
      "in".
    filter_bank
      The parent filter bank that this shutter is a part of. This
      *filter_bank*'s *setpoint* and *readback* signals will be used
      for actuating both shutter blades together.

    """

    _ophyd_labels_ = {"shutters", "fast_shutters"}

    def __init__(
        self,
        prefix: str,
        *,
        name: str = "",
        top_filter: int,
        bottom_filter: int,
        filter_bank: PFCUFilterBank,
        **kwargs,
    ):
        self._top_filter_idx = top_filter
        self._bottom_filter_idx = bottom_filter
        with self.add_children_as_readables():
            self.bottom_filter = PFCUFilter(prefix=f"{prefix}filter{bottom_filter+1}")
            self.top_filter = PFCUFilter(prefix=f"{prefix}filter{top_filter+1}")
        # Set up the positioner signals
        parent_signals = {
            "setpoint": filter_bank.setpoint,
            "readback": filter_bank.readback,
        }
        self.setpoint = derived_signal_rw(
            int, derived_from=parent_signals, forward=self.forward, inverse=self.inverse
        )
        with self.add_children_as_readables():
            self.readback = derived_signal_r(
                int, derived_from=parent_signals, inverse=self.inverse
            )
        # Just use convenient values for positioner signals since there's no real position
        self.velocity = soft_signal_rw(float, initial_value=0.5)
        self.units = soft_signal_rw(str, initial_value="")
        self.precision = soft_signal_rw(int, initial_value=0)
        super().__init__(
            name=name,
            put_complete=True,
            **kwargs,
        )

    async def forward(self, value, setpoint, readback):
        """Convert shutter state to filter bank state."""
        # Bit masking to set both blades together
        readback_value = await readback.get_value()
        num_bits = len(readback_value)
        old_bits = int(readback_value, 2)
        if value == ShutterState.OPEN:
            open_bits = self.bottom_mask()
            close_bits = self.top_mask()
        elif value == ShutterState.CLOSED:
            close_bits = self.bottom_mask()
            open_bits = self.top_mask()
        else:
            raise ValueError(bin(value))
        new_bits = (old_bits | open_bits) & (0b1111 - close_bits)
        log.debug(f"{old_bits=:b}, {open_bits=:b}, {close_bits=:b}, {new_bits=:b}")
        return {setpoint: f"{new_bits:0b}".zfill(num_bits)}

    def inverse(self, values, readback, **kwargs):
        """Convert filter bank state to shutter state."""
        bits = int(values[readback], 2)
        # Determine which filters are open and closed
        top_position = int(bool(bits & self.top_mask()))
        bottom_position = int(bool(bits & self.bottom_mask()))
        result = shutter_state_map[(top_position, bottom_position)]
        return result

    def _mask(self, pos):
        num_filters = 4
        return 1 << (num_filters - pos - 1)

    def top_mask(self):
        return self._mask(self._top_filter_idx)

    def bottom_mask(self):
        return self._mask(self._bottom_filter_idx)


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
