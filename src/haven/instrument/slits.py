"""This is a copy of the apstools Slits support with signals for the tweak PV."""

import logging

from apstools.devices import PVPositionerSoftDone
from apstools.synApps.db_2slit import Optics2Slit1D, Optics2Slit2D_HV
from ophyd import Component as Cpt
from ophyd import DerivedSignal, Device, EpicsSignal
from ophyd import FormattedComponent as FCpt

from .. import exceptions
from .._iconfig import load_config
from .device import make_device
from .motor import HavenMotor

log = logging.getLogger(__name__)


class PVPositionerWithTweaks(PVPositionerSoftDone):
    user_readback = Cpt(DerivedSignal, derived_from="readback")
    user_setpoint = Cpt(DerivedSignal, derived_from="setpoint")
    tweak_value = FCpt(EpicsSignal, "{prefix}{_setpoint_pv}_tweakVal.VAL")
    tweak_forward = FCpt(EpicsSignal, "{prefix}{_setpoint_pv}_tweak.B")
    tweak_reverse = FCpt(EpicsSignal, "{prefix}{_setpoint_pv}_tweak.A")


class BladePair(Optics2Slit1D):
    """
    EPICS synApps optics 2slit.db 1D support: xn, xp, size, center, sync

    "sync" is used to tell the EPICS 2slit database to synchronize the
    virtual slit values with the actual motor positions.
    """

    # Override these components to include the tweak signals
    xn = Cpt(PVPositionerWithTweaks, "", setpoint_pv="xn", readback_pv="t2.B")
    xp = Cpt(PVPositionerWithTweaks, "", setpoint_pv="xp", readback_pv="t2.A")
    size = Cpt(PVPositionerWithTweaks, "", setpoint_pv="size", readback_pv="t2.C")
    center = Cpt(PVPositionerWithTweaks, "", setpoint_pv="center", readback_pv="t2.D")


class BladeSlits(Optics2Slit2D_HV):
    """Set of slits with blades that move in and out to control beam size."""

    h = Cpt(BladePair, "H")
    v = Cpt(BladePair, "V")


class SlitMotor(HavenMotor):
    """An Ophyd device for a motor on a set of slits.

    Similar to a regular motor with extra signals to give it the same
    interface as a non-motor based slit parameter. Different
    implementations of the slits support either provide pseudo motors,
    or a different kind of record.

    """

    readback = Cpt(DerivedSignal, derived_from="user_readback")
    setpoint = Cpt(DerivedSignal, derived_from="user_setpoint")


class ApertureSlits(Device):
    """A rotating aperture that functions like a set of slits.

    Unlike the blades slits, there are no independent parts to move,
    so each axis only has center and size.

    Based on the 25-ID-A whitebeam slits.

    The motor parameters listed below specify which motor records
    control which axis. The last piece of the PV prefix will be
    removed, and the motor number added on. For example, if the prefix
    is "255ida:slits:US:", and the pitch motor is "255ida:slits:m3",
    then *pitch_motor* should be "m3".

    Parameters
    ==========
    pitch_motor
      The motor record suffix controlling the real pitch motor. Don't
      include a field. E.g. "m3"
    yaw_motor
      The motor record suffix controlling the real yaw motor. Don't
      include a field. E.g. "m3"
    horizontal_motor
      The motor record suffix controlling the real horizontal
      motor. This is different from the horizontal slits
      position. Don't include a field. E.g. "m3"
    diagonal_motor
      The motor record suffix controlling the real diagonal
      motor. Don't include a field. E.g. "m3"

    """

    def __init__(
        self,
        prefix: str,
        *args,
        pitch_motor: str,
        yaw_motor: str,
        horizontal_motor: str,
        diagonal_motor: str,
        **kwargs,
    ):
        # Determine the prefix for the motors
        pieces = prefix.strip(":").split(":")
        self.motor_prefix = ":".join(pieces[:-1])
        self._pitch_motor = pitch_motor
        self._yaw_motor = yaw_motor
        self._horizontal_motor = horizontal_motor
        self._diagonal_motor = diagonal_motor
        super().__init__(prefix, *args, **kwargs)

    class SlitAxis(Device):
        size = Cpt(SlitMotor, "Size", labels={"motors"})
        center = Cpt(SlitMotor, "Center", labels={"motors"})

    # Individual slit directions
    h = Cpt(SlitAxis, "h")
    v = Cpt(SlitAxis, "v")

    # Real motors that directly control the slits
    pitch = FCpt(
        SlitMotor, "{self.motor_prefix}:{self._pitch_motor}", labels={"motors"}
    )
    yaw = FCpt(SlitMotor, "{self.motor_prefix}:{self._yaw_motor}", labels={"motors"})
    horizontal = FCpt(
        SlitMotor, "{self.motor_prefix}:{self._horizontal_motor}", labels={"motors"}
    )
    diagonal = FCpt(
        SlitMotor, "{self.motor_prefix}:{self._diagonal_motor}", labels={"motors"}
    )


def load_slits(config=None):
    if config is None:
        config = load_config()
    # Create slits
    devices = []
    for name, slit_config in config.get("slits", {}).items():
        DeviceClass = globals().get(slit_config["device_class"])
        prefix = slit_config["prefix"]
        # Check that it's a valid device class
        if DeviceClass is None:
            msg = f"slits.{name}.device_class={slit_config['device_class']}"
            raise exceptions.UnknownDeviceConfiguration(msg)
        ioc_prefix = prefix.split(":")[0]
        # Determine real motor PVs
        motors = {}
        if DeviceClass is ApertureSlits:
            try:
                motors.update(
                    dict(
                        horizontal_motor=slit_config["horizontal_motor"],
                        diagonal_motor=slit_config["diagonal_motor"],
                        pitch_motor=slit_config["pitch_motor"],
                        yaw_motor=slit_config["yaw_motor"],
                    )
                )
            except KeyError:
                msg = f"Missing motors for slits.{name}.device_class={slit_config['device_class']}"
                raise exceptions.UnknownDeviceConfiguration(msg)
        # Create the device
        devices.append(
            make_device(
                DeviceClass,
                prefix=prefix,
                name=name,
                labels={"slits"},
                **motors,
            )
        )
    return devices


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
