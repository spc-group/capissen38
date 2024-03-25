import asyncio
import logging

from ophyd import Component as Cpt
from ophyd import EpicsMotor, EpicsSignal, EpicsSignalRO
from ophyd import FormattedComponent as FCpt
from ophyd import PseudoPositioner, PseudoSingle, PVPositioner
from ophyd.ophydobj import OphydObject
from ophyd.pseudopos import pseudo_position_argument, real_position_argument

from .._iconfig import load_config
from .device import aload_devices, await_for_connection
from .instrument_registry import registry
from .monochromator import IDTracking, Monochromator

log = logging.getLogger(__name__)


__all__ = ["EnergyPositioner", "load_energy_positioner"]


class Undulator(PVPositioner):
    setpoint = Cpt(EpicsSignal, ":ScanEnergy.VAL")
    readback = Cpt(EpicsSignalRO, ":Energy.VAL")
    done = Cpt(EpicsSignalRO, ":Busy.VAL", kind="omitted")
    stop_signal = Cpt(EpicsSignal, ":Stop.VAL", kind="omitted")


class EnergyPositioner(PseudoPositioner):
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
    mono_pv
      The process variable for the monochromator energy PV.
    id_prefix
      The prefix for the insertion device energy, such that
      f"{id_prefix}:Energy.VAL" reaches the energy readback value.
    id_offset_pv
      The PV address for the offset between monochromator and
      insertion device.
    id_tracking_pv
      The PV address for whether the ID gets tracked automatically in
      EPICS.

    """

    # Pseudo axes
    energy: OphydObject = Cpt(PseudoSingle, kind="hinted")

    # Equivalent real axes
    mono_energy: OphydObject = FCpt(EpicsMotor, "{mono_pv}", kind="normal")
    # id_offset: float = 300.  # In eV
    id_tracking: OphydObject = FCpt(EpicsSignal, "{id_tracking_pv}", kind="config")
    id_offset: OphydObject = FCpt(EpicsSignal, "{id_offset_pv}", kind="config")
    id_energy: OphydObject = FCpt(Undulator, "{id_prefix}", kind="normal")

    def __init__(
        self,
        mono_pv: str,
        id_prefix: str,
        id_offset_pv: str,
        id_tracking_pv: str,
        *args,
        **kwargs,
    ):
        """INIT DOCSTRING"""
        self.mono_pv = mono_pv
        self.id_offset_pv = id_offset_pv
        self.id_prefix = id_prefix
        self.id_tracking_pv = id_tracking_pv
        super().__init__(*args, **kwargs)
        self.stage_sigs[self.id_tracking] = IDTracking.OFF

    @pseudo_position_argument
    def forward(self, target_energy):
        "Given a target energy, transform to the mono and ID energies."
        id_offset_ev = self.id_offset.get(use_monitor=True)
        return self.RealPosition(
            mono_energy=target_energy.energy,
            id_energy=(target_energy.energy + id_offset_ev) / 1000.0,
        )

    @real_position_argument
    def inverse(self, device_energy):
        "Given a position in mono and ID energy, transform to the target energy."
        return self.PseudoPosition(
            energy=device_energy.mono_energy,
        )


async def make_energy_device(
    name, mono_prefix, mono_suffix, id_prefix, id_offset_suffix, id_tracking_suffix
):
    dev = EnergyPositioner(
        name=name,
        mono_pv=f"{mono_prefix}{mono_suffix}",
        id_offset_pv=f"{mono_prefix}{id_offset_suffix}",
        id_tracking_pv=f"{mono_prefix}{id_tracking_suffix}",
        id_prefix=id_prefix,
    )
    try:
        await await_for_connection(dev)
    except TimeoutError as exc:
        msg = f"Could not connect to energy positioner: {name}"
        log.warning(msg)
    else:
        return dev


def load_energy_positioner_coros(config=None):
    # Load PV's from config
    if config is None:
        config = load_config()
    # Guard to make sure we have a mono and ID configuration
    if "monochromator" not in config.keys() or "undulator" not in config.keys():
        return
    # Make the combined energy device
    yield make_energy_device(
        name="energy",
        mono_suffix=Monochromator.energy.suffix,
        id_offset_suffix=Monochromator.id_offset.suffix,
        id_tracking_suffix=Monochromator.id_tracking.suffix,
        mono_prefix=config["monochromator"]["ioc"],
        id_prefix=config["undulator"]["ioc"],
    )


def load_energy_positioner(config=None):
    asyncio.run(aload_devices(*load_energy_positioner_coros(config=config)))


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
