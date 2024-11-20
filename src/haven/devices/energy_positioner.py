import logging

from ophyd_async.core import (
    CALCULATE_TIMEOUT,
    AsyncStatus,
    CalculatableTimeout,
    Signal,
    StandardReadableFormat,
)

from ..positioner import Positioner
from .monochromator import Monochromator
from .signal import derived_signal_r, derived_signal_rw
from .xray_source import PlanarUndulator

log = logging.getLogger(__name__)


__all__ = ["EnergyPositioner"]


class EnergyPositioner(Positioner):
    """The operational energy of the beamline.

    Responsible for setting both mono and ID energy with an optional
    ID offset. Setting the *energy* component will propagate to both
    real devices and so ``EnergyPositioner().energy`` is a good
    candidate for a positioner for Bluesky plans.

    Currently, the offset between the insertion device and the
    monochromator is fixed. In the future this will be replaced with a
    more sophisticated calculation.

    .. todo::

       Insert functionality to have a non-constant ID offset.

    Attributes
    ==========

    id_offset
      The offset for the insertion device relative to the mono energy.
    energy
      The pseudo positioner for the forward calculation.
    mono_energy
      The real component for the monochromator energy.
    id_energy
      The real component for the insertion device energy.

    Parameters
    ==========
    monochromator_prefix
      The CA prefix for the monochromator IOC.
    undulator_prefix
      The prefix for the insertion device energy, such that
      f"{id_prefix}:Energy.VAL" reaches the energy readback value.

    """

    _ophyd_labels_ = {"energy"}

    def __init__(
        self,
        monochromator_prefix: str,
        undulator_prefix: str,
        name: str = "energy",
    ):
        self.monochromator = Monochromator(monochromator_prefix)
        self.undulator = PlanarUndulator(undulator_prefix)
        # Derived positioner signals
        self.setpoint = derived_signal_rw(
            float,
            derived_from={
                "mono": self.monochromator.energy.user_setpoint,
                "undulator": self.undulator.energy.setpoint,
            },
            forward=self.set_energy,
            inverse=self.get_energy,
        )
        with self.add_children_as_readables(StandardReadableFormat.HINTED_SIGNAL):
            self.readback = derived_signal_r(
                float,
                derived_from={"mono": self.monochromator.energy.user_readback},
                inverse=self.get_energy,
            )
        # Additional derived signals
        self.precision = derived_signal_rw(
            int, derived_from={"precision": self.monochromator.energy.precision}
        )
        self.units = derived_signal_rw(
            str, derived_from={"units": self.monochromator.energy.motor_egu}
        )
        self.velocity = derived_signal_rw(
            float, derived_from={"velocity": self.monochromator.energy.velocity}
        )

        super().__init__(name=name, put_complete=True)

    async def set_energy(self, value, mono: Signal, undulator: Signal):
        ev_per_kev = 1000
        offset = await self.monochromator.id_offset.get_value()
        vals = {
            self.monochromator.energy: value,
            self.undulator.energy: (value + offset) / ev_per_kev,
        }
        return vals

    def get_energy(self, values, mono: float, undulator: Signal | None = None):
        # Use just the mono value as a readback
        return values[mono]

    @AsyncStatus.wrap
    async def set(
        self, value: float, wait=True, timeout: CalculatableTimeout = CALCULATE_TIMEOUT
    ):

        # Turn off the mono-ID tracking in the EPICS IOC since it
        # conflicts with the Haven equivalent
        was_tracking = await self.monochromator.id_tracking.get_value()
        await self.monochromator.id_tracking.set(False)
        # Set the actual energy on the mono
        await super().set(value=value, wait=wait, timeout=timeout)
        # Restore mono-ID tracking if it was previously enabled
        if bool(was_tracking):
            await self.monochromator.id_tracking.set(True)


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
