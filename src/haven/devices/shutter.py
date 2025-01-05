import logging
import warnings
from enum import IntEnum, unique
from typing import Mapping

from ophyd.utils.errors import ReadOnlyError
from ophyd_async.core import soft_signal_rw
from ophyd_async.epics.core import epics_signal_r

from ..positioner import Positioner
from .signal import derived_signal_rw, epics_signal_xval

__all__ = ["PssShutter", "ShutterState"]


log = logging.getLogger(__name__)


@unique
class ShutterState(IntEnum):
    OPEN = 0  # 0b000
    CLOSED = 1  # 0b001
    FAULT = 3  # 0b011
    UNKNOWN = 4  # 0b100


class PssShutter(Positioner):
    _ophyd_labels_ = {"shutters"}
    _last_setpoint: int = ShutterState.UNKNOWN
    allow_open: bool
    allow_close: bool

    def __init__(
        self,
        prefix: str,
        name: str,
        allow_open: bool = True,
        allow_close: bool = True,
        labels={"shutters"},
        **kwargs,
    ):
        self.allow_open = allow_open
        self.allow_close = allow_close
        # Actuators for opening/closing the shutter
        self.open_signal = epics_signal_xval(f"{prefix}OpenEPICSC")
        self.close_signal = epics_signal_xval(f"{prefix}CloseEPICSC")
        # Just use convenient values for these since there's no real position
        self.velocity = soft_signal_rw(float, initial_value=0.5)
        self.units = soft_signal_rw(str, initial_value="")
        self.precision = soft_signal_rw(int, initial_value=0)
        # Positioner signals for moving the shutter
        with self.add_children_as_readables():
            self.readback = epics_signal_r(bool, f"{prefix}BeamBlockingM.VAL")
        self.setpoint = derived_signal_rw(
            int,
            derived_from={
                "open_signal": self.open_signal,
                "close_signal": self.close_signal,
            },
            forward=self._actuate_shutter,
            inverse=self._shutter_setpoint,
        )
        super().__init__(name=name, **kwargs)

    def check_value(self, pos):
        """Check that the shutter has the right permissions."""
        if pos == ShutterState.CLOSED and not self.allow_close:
            raise ReadOnlyError(
                f"Shutter {self.name} is not permitted to be closed. Set `allow_close` for this shutter."
            )
        if pos == ShutterState.OPEN and not self.allow_open:
            raise ReadOnlyError(
                f"Shutter {self.name} is not permitted to be opened per iconfig.toml. Set `allow_open` for this shutter."
            )

    async def _actuate_shutter(self, value: int, open_signal, close_signal) -> Mapping:
        """Open/close the shutter using derived-from signals."""
        self.check_value(value)
        if value == ShutterState.OPEN:
            items = {open_signal: 1}
        elif value == ShutterState.CLOSED:
            items = {close_signal: 1}
        else:
            raise ValueError(f"Invalid shutter state for {self}")
        return items

    def _shutter_setpoint(self, values: Mapping, open_signal, close_signal) -> int:
        """Determine whether the shutter was last opened or closed."""
        do_open = values[open_signal]
        do_close = values[close_signal]
        if do_open and do_close:
            # Shutter is both opening and closing??
            warnings.warn("Unknown shutter setpoint")
            self._last_setpoint = ShutterState.UNKNOWN
        elif do_open:
            self._last_setpoint = ShutterState.OPEN
        elif do_close:
            self._last_setpoint = ShutterState.CLOSED
        return self._last_setpoint


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
