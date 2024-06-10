"""Ophyd device support for a set of XIA PFCU-controlled filters.

A PFCUFilterBank controls a set of 4 filters. Optionally, 2 filters in
a filter bank can be used as a shutter.

"""

from enum import IntEnum

from ophyd import Component as Cpt
from ophyd import DynamicDeviceComponent as DCpt
from ophyd import EpicsSignal, EpicsSignalRO
from ophyd import FormattedComponent as FCpt
from ophyd import PVPositionerIsClose
from ophyd.signal import DerivedSignal

from .. import exceptions
from .._iconfig import load_config
from .device import make_device


class FilterPosition(IntEnum):
    OUT = 0
    IN = 1


class PFCUFilter(PVPositionerIsClose):
    """A single filter in a PFCU filter bank.

    E.g. 25idc:pfcu0:filter1_mat
    """

    material = Cpt(EpicsSignal, "_mat", kind="config")
    thickness = Cpt(EpicsSignal, "_thick", kind="config")
    thickness_unit = Cpt(EpicsSignal, "_thick.EGU", kind="config")
    notes = Cpt(EpicsSignal, "_other", kind="config")

    setpoint = Cpt(EpicsSignal, "", kind="normal")
    readback = Cpt(EpicsSignalRO, "_RBV", kind="normal")


class ShutterStates(IntEnum):
    OPEN = 0  # 0b000
    CLOSED = 1  # 0b001
    HALF_CLOSED = 3  # 0b011
    UNKNOWN = 4  # 0b100


shutter_state_map = {
    # (top filter, bottom filter): state
    (FilterPosition.OUT, FilterPosition.IN): ShutterStates.OPEN,
    (FilterPosition.IN, FilterPosition.OUT): ShutterStates.CLOSED,
    (FilterPosition.OUT, FilterPosition.OUT): ShutterStates.HALF_CLOSED,
    (FilterPosition.IN, FilterPosition.IN): ShutterStates.HALF_CLOSED,
}


class PFCUShutterSignal(DerivedSignal):
    def _mask(self, pos):
        num_filters = 4
        return 1 << (num_filters - pos)

    def top_mask(self):
        return self._mask(self.parent._top_filter)

    def bottom_mask(self):
        return self._mask(self.parent._bottom_filter)

    def forward(self, value):
        """Convert shutter state to filter bank state."""
        # Bit masking to set both blades together
        old_bits = self.derived_from.parent.readback.get(as_string=False)
        if value == ShutterStates.OPEN:
            open_bits = self.bottom_mask()
            close_bits = self.top_mask()
        elif value == ShutterStates.CLOSED:
            close_bits = self.bottom_mask()
            open_bits = self.top_mask()
        else:
            raise ValueError(bin(value))
        new_bits = (old_bits | open_bits) & (0b1111 - close_bits)
        return new_bits

    def inverse(self, value):
        """Convert filter bank state to shutter state."""
        # Determine which filters are open and closed
        top_position = int(bool(value & self.top_mask()))
        bottom_position = int(bool(value & self.bottom_mask()))
        result = shutter_state_map[(top_position, bottom_position)]
        return result


class PFCUShutter(PVPositionerIsClose):
    """A shutter made of two PFCU4 filters.

    For faster operation, both filters will be moved at the same
    time. That means this shutter must be a sub-component of a
    :py:class:`PFCUFilterBank`.

    Parameters
    ==========
    top_filter
      The PV for the filter that is open when the filter is set to
      "out".
    bottom_filter
      The PV for the filter that is open when the filter is set to
      "in".

    """

    readback = Cpt(PFCUShutterSignal, derived_from="parent.parent.readback")
    setpoint = Cpt(PFCUShutterSignal, derived_from="parent.parent.setpoint")

    top_filter = FCpt(PFCUFilter, "{self.prefix}filter{self._top_filter}")
    bottom_filter = FCpt(PFCUFilter, "{self.prefix}filter{self._bottom_filter}")

    def __init__(self, *args, top_filter: str, bottom_filter: str, **kwargs):
        self._top_filter = top_filter
        self._bottom_filter = bottom_filter
        super().__init__(
            *args, limits=(ShutterStates.OPEN, ShutterStates.CLOSED), **kwargs
        )


class PFCUFilterBank(PVPositionerIsClose):
    """Parameters
    ==========
    shutters
      Sets of filter numbers to use as shutters. Each entry in
      *shutters* should be a tuple like (top, bottom) where the first
      filter (top) is open when the filter is set to "out".

    """

    num_slots: int = 4

    readback = Cpt(EpicsSignalRO, "config_RBV", kind="normal")
    setpoint = Cpt(EpicsSignal, "config", kind="normal")

    def __new__(cls, *args, shutters=[], **kwargs):
        # Determine which filters to use as filters vs shutters
        all_shutters = [v for shutter in shutters for v in shutter]
        filters = [
            idx for idx in range(1, cls.num_slots + 1) if idx not in all_shutters
        ]
        # Create device components for filters and shutters
        comps = {
            "shutters": DCpt(
                {
                    f"shutter_{idx}": (
                        PFCUShutter,
                        "",
                        {
                            "top_filter": top,
                            "bottom_filter": bottom,
                            "labels": {"shutters"},
                        },
                    )
                    for idx, (top, bottom) in enumerate(shutters)
                }
            ),
            "filters": DCpt(
                {
                    f"filter{idx}": (
                        PFCUFilter,
                        f"filter{idx}",
                        {"labels": {"filters"}},
                    )
                    for idx in filters
                }
            ),
        }
        # Create any new child class with shutters and filters
        new_cls = type(cls.__name__, (PFCUFilterBank,), comps)
        return object.__new__(new_cls)

    def __init__(
        self,
        *args,
        shutters=[],
        **kwargs,
    ):
        super().__init__(*args, **kwargs)


def load_xia_pfcu4s(config=None):
    if config is None:
        config = load_config()
    # Read the filter bank configurations from the config file
    devices = []
    for name, cfg in config.get("pfcu4", {}).items():
        try:
            prefix = cfg["prefix"]
            shutters = cfg.get("shutters", [])
        except KeyError as ex:
            raise exceptions.UnknownDeviceConfiguration(
                f"Device {name} missing '{ex.args[0]}': {cfg}"
            ) from ex
        # Make the device
        devices.append(
            make_device(
                PFCUFilterBank,
                prefix=prefix,
                name=name,
                shutters=shutters,
                labels={"filter_banks"},
            )
        )
    return devices


# def load_xia_pfcu4s(config=None):
#     asyncio.run(aload_devices(*load_xia_pfcu4_coros(config=config)))


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
