import logging
from enum import IntEnum

from ophyd import Component as Cpt
from ophyd import Device, EpicsMotor, EpicsSignal, EpicsSignalRO

from .._iconfig import load_config
from .device import make_device

log = logging.getLogger(__name__)


class IDTracking(IntEnum):
    OFF = 0
    ON = 1


class Monochromator(Device):
    # ID tracking PVs
    id_tracking = Cpt(EpicsSignal, ":ID_tracking", kind="config")
    id_offset = Cpt(EpicsSignal, ":ID_offset", kind="config")
    d_spacing = Cpt(EpicsSignal, ":dspacing", kind="config")
    # Virtual positioners
    mode = Cpt(EpicsSignal, ":mode", labels={"motors", "baseline"}, kind="config")
    energy = Cpt(EpicsMotor, ":Energy", labels={"motors"}, kind="hinted")
    energy_constant1 = Cpt(
        EpicsSignal, ":EnergyC1.VAL", labels={"baseline"}, kind="config"
    )
    energy_constant2 = Cpt(
        EpicsSignal, ":EnergyC2.VAL", labels={"baseline"}, kind="config"
    )
    energy_constant3 = Cpt(
        EpicsSignal, ":EnergyC3.VAL", labels={"baseline"}, kind="config"
    )
    offset = Cpt(EpicsMotor, ":Offset", labels={"motors", "baseline"}, kind="config")
    # ACS Motors
    horiz = Cpt(EpicsMotor, ":ACS:m1", labels={"motors", "baseline"}, kind="config")
    vert = Cpt(EpicsMotor, ":ACS:m2", labels={"motors", "baseline"}, kind="config")
    bragg = Cpt(EpicsMotor, ":ACS:m3", labels={"motors"})
    gap = Cpt(EpicsMotor, ":ACS:m4", labels={"motors"})
    roll2 = Cpt(EpicsMotor, ":ACS:m5", labels={"motors", "baseline"}, kind="config")
    pitch2 = Cpt(EpicsMotor, ":ACS:m6", labels={"motors", "baseline"}, kind="config")
    roll_int = Cpt(EpicsMotor, ":ACS:m7", labels={"motors", "baseline"}, kind="config")
    pi_int = Cpt(EpicsMotor, ":ACS:m8", labels={"motors", "baseline"}, kind="config")
    # Physical constants
    d_spacing = Cpt(EpicsSignalRO, ":dspacing", labels={"baseline"}, kind="config")


def load_monochromators(config=None):
    # Load PV's from config
    if config is None:
        config = load_config()
    # Guard to make sure there's at least one mono configuration
    if "monochromator" not in config.keys():
        return []
    # Load mono device from configuration
    prefix = config["monochromator"]["ioc"]
    mono = make_device(
        Monochromator, name="monochromator", labels={"monochromators"}, prefix=prefix
    )
    return [mono]


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
