import logging
from enum import IntEnum

from ophyd_async.core import (
    Signal,
    StandardReadable,
    StandardReadableFormat,
    SubsetEnum,
    soft_signal_rw,
)
from ophyd_async.epics.core import epics_signal_r, epics_signal_rw, epics_signal_x

from ..positioner import Positioner
from .signal import derived_signal_r, derived_signal_x

log = logging.getLogger(__name__)


class DoneStatus(IntEnum):
    MOVING = 0
    DONE = 1


class BusyStatus(IntEnum):
    DONE = 0
    BUSY = 1


class MotorDriveStatus(IntEnum):
    NOT_READY = 0
    READY_TO_MOVE = 1


class UndulatorPositioner(Positioner):
    done_value: int = BusyStatus.DONE

    def __init__(
        self,
        *,
        prefix: str,
        actuate_signal: Signal = None,
        stop_signal: Signal,
        done_signal: Signal = None,
        name: str = "",
        min_move: float = 0.0,
    ):
        with self.add_children_as_readables(StandardReadableFormat.HINTED_SIGNAL):
            self.readback = epics_signal_rw(float, f"{prefix}M.VAL")
        with self.add_children_as_readables():
            self.setpoint = epics_signal_rw(float, f"{prefix}SetC.VAL")
        with self.add_children_as_readables(StandardReadableFormat.CONFIG_SIGNAL):
            self.units = epics_signal_r(str, f"{prefix}SetC.EGU")
            self.precision = epics_signal_r(int, f"{prefix}SetC.PREC")
        self.velocity = soft_signal_rw(
            float, initial_value=1
        )  # Need to figure out what this value is
        # Add control signals that depend on the parent
        if actuate_signal is not None:
            self.actuate = derived_signal_x(
                derived_from={"parent_signal": actuate_signal}
            )
        self.stop_signal = derived_signal_x(derived_from={"parent_signal": stop_signal})
        if done_signal is not None:
            self.done = derived_signal_r(
                int, derived_from={"parent_signal": done_signal}
            )
        super().__init__(name=name, min_move=min_move)


class PlanarUndulator(StandardReadable):
    """APS Planar Undulator

    .. index:: Ophyd Device; PlanarUndulator

    The signals *busy* and *done* convey complementary
    information. *busy* comes from the IOC, while *done* comes
    directly from the controller.

    EXAMPLE::

        undulator = PlanarUndulator("S25ID:USID:", name="undulator")

    """

    _ophyd_labels_ = {"xray_sources", "undulators"}

    class AccessMode(SubsetEnum):
        USER = "User"
        OPERATOR = "Operator"
        MACHINE_PHYSICS = "Machine Physics"
        SYSTEM_MANAGER = "System Manager"

    def __init__(self, prefix: str, name: str = ""):
        # Signals for moving the undulator
        self.start_button = epics_signal_x(f"{prefix}StartC.VAL")
        self.stop_button = epics_signal_x(f"{prefix}StopC.VAL")
        self.busy = epics_signal_r(bool, f"{prefix}BusyM.VAL")
        self.done = epics_signal_r(bool, f"{prefix}BusyDeviceM.VAL")
        self.motor_drive_status = epics_signal_r(int, f"{prefix}MotorDriveStatusM.VAL")
        # Configuration state for the undulator
        with self.add_children_as_readables(StandardReadableFormat.CONFIG_SIGNAL):
            self.harmonic_value = epics_signal_rw(int, f"{prefix}HarmonicValueC")
            self.total_power = epics_signal_r(float, f"{prefix}TotalPowerM.VAL")
            self.gap_deadband = epics_signal_rw(int, f"{prefix}DeadbandGapC")
            self.device_limit = epics_signal_rw(float, f"{prefix}DeviceLimitM.VAL")
            self.device = epics_signal_r(str, f"{prefix}DeviceM")
            self.magnet = epics_signal_r(str, f"{prefix}DeviceMagnetM")
            self.location = epics_signal_r(str, f"{prefix}LocationM")
            self.version_plc = epics_signal_r(float, f"{prefix}PLCVersionM.VAL")
            self.version_hpmu = epics_signal_r(str, f"{prefix}HPMUVersionM.VAL")
        # X-ray spectrum positioners
        with self.add_children_as_readables():
            self.energy = UndulatorPositioner(
                prefix=f"{prefix}Energy",
                actuate_signal=self.start_button,
                stop_signal=self.stop_button,
                done_signal=self.busy,
                min_move=0.0,
            )
            self.energy_taper = UndulatorPositioner(
                prefix=f"{prefix}TaperEnergy",
                actuate_signal=self.start_button,
                stop_signal=self.stop_button,
                done_signal=self.busy,
            )
            self.gap = UndulatorPositioner(
                prefix=f"{prefix}Gap",
                actuate_signal=self.start_button,
                stop_signal=self.stop_button,
                done_signal=self.busy,
                min_move=0.0,
            )
            self.gap_taper = UndulatorPositioner(
                prefix=f"{prefix}TaperGap",
                actuate_signal=self.start_button,
                stop_signal=self.stop_button,
                done_signal=self.busy,
            )
        # Miscellaneous control signals
        self.access_mode = epics_signal_r(self.AccessMode, f"{prefix}AccessSecurityC")
        self.message1 = epics_signal_r(str, f"{prefix}Message1M.VAL")
        self.message2 = epics_signal_r(str, f"{prefix}Message2M.VAL")

        super().__init__(name=name)


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
