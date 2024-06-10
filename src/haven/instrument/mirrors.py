from apstools.synApps import TransformRecord
from ophyd import Component as Cpt
from ophyd import Device
from ophyd import FormattedComponent as FCpt
from ophyd import Kind

from .. import exceptions
from .._iconfig import load_config
from .device import RegexComponent as RCpt
from .device import make_device
from .motor import HavenMotor


class HighHeatLoadMirror(Device):
    bendable = False
    # Physical motors
    transverse = Cpt(HavenMotor, "m1", labels={"motors"})
    roll = Cpt(HavenMotor, "m2", labels={"motors"})
    upstream = Cpt(HavenMotor, "m3", labels={"motors"})
    downstream = Cpt(HavenMotor, "m4", labels={"motors"})

    # Pseudo motors
    pitch = Cpt(HavenMotor, "coarsePitch", kind=Kind.hinted, labels={"motors"})
    normal = Cpt(HavenMotor, "lateral", kind=Kind.hinted, labels={"motors"})

    # Standard transform records for the pseudo motors
    drive_transform = Cpt(TransformRecord, "lats:Drive", kind=Kind.config)
    readback_transform = Cpt(TransformRecord, "lats:Readback", kind=Kind.config)


class BendableHighHeatLoadMirror(HighHeatLoadMirror):
    bendable = True
    bender = Cpt(HavenMotor, "m5", labels={"motors"})


class KBMirror(Device):
    """A single mirror in a KB mirror set."""

    bendable = False

    pitch = Cpt(HavenMotor, "pitch", labels={"motors"})
    normal = Cpt(HavenMotor, "height", labels={"motors"})
    upstream = FCpt(HavenMotor, "{upstream_motor}", labels={"motors"})
    downstream = FCpt(HavenMotor, "{downstream_motor}", labels={"motors"})

    # The pseudo motor transform records have
    # a missing ':', so we need to remove it.
    drive_transform = RCpt(
        TransformRecord, "Drive", pattern=":([HV]):", repl=r"\1:", kind=Kind.config
    )
    readback_transform = RCpt(
        TransformRecord, "Readback", pattern=":([HV]):", repl=r"\1:", kind=Kind.config
    )

    def __init__(
        self,
        *args,
        upstream_motor: str,
        downstream_motor: str,
        upstream_bender: str = "",
        downstream_bender: str = "",
        **kwargs,
    ):
        self.upstream_motor = upstream_motor
        self.downstream_motor = downstream_motor
        self._upstream_bender = upstream_bender
        self._downstream_bender = downstream_bender
        super().__init__(*args, **kwargs)


class BendableKBMirror(KBMirror):
    """A single bendable mirror in a KB mirror set."""

    bendable = True

    bender_upstream = FCpt(HavenMotor, "{_upstream_bender}", labels={"motors"})
    bender_downstream = FCpt(HavenMotor, "{_downstream_bender}", labels={"motors"})


class KBMirrors(Device):
    def __new__(
        cls,
        *args,
        horiz_upstream_motor: str,
        horiz_downstream_motor: str,
        vert_upstream_motor: str,
        vert_downstream_motor: str,
        horiz_upstream_bender: str = "",
        horiz_downstream_bender: str = "",
        vert_upstream_bender: str = "",
        vert_downstream_bender: str = "",
        **kwargs,
    ):
        # Decide if the mirrors are bendable or not
        HorizClass = VertClass = KBMirror
        if bool(horiz_upstream_bender) and bool(horiz_downstream_bender):
            HorizClass = BendableKBMirror
        if bool(vert_upstream_bender) and bool(vert_downstream_bender):
            VertClass = BendableKBMirror
        # Create a customized subclass based on the configuration attrs
        attrs = dict(
            horiz=Cpt(
                HorizClass,
                "H:",
                upstream_motor=horiz_upstream_motor,
                downstream_motor=horiz_downstream_motor,
                upstream_bender=horiz_upstream_bender,
                downstream_bender=horiz_downstream_bender,
            ),
            vert=Cpt(
                VertClass,
                "V:",
                upstream_motor=vert_upstream_motor,
                downstream_motor=vert_downstream_motor,
                upstream_bender=vert_upstream_bender,
                downstream_bender=vert_downstream_bender,
            ),
        )
        NewMirrors = type("KBMirrors", (cls,), attrs)
        return super().__new__(NewMirrors)

    def __init__(
        self,
        *args,
        horiz_upstream_motor: str,
        horiz_downstream_motor: str,
        vert_upstream_motor: str,
        vert_downstream_motor: str,
        horiz_upstream_bender: str = "",
        horiz_downstream_bender: str = "",
        vert_upstream_bender: str = "",
        vert_downstream_bender: str = "",
        **kwargs,
    ):
        super().__init__(*args, **kwargs)


def load_mirrors(config=None):
    if config is None:
        config = load_config()
    # Create two-bounce KB mirror sets
    devices = []
    for name, kb_config in config.get("kb_mirrors", {}).items():
        # Build the motor prefixes
        try:
            prefix = kb_config["prefix"]
            ioc_prefix = prefix.split(":")[0]
            motors = dict(
                # Normal motors
                horiz_upstream_motor=kb_config["horiz_upstream_motor"],
                horiz_downstream_motor=kb_config["horiz_downstream_motor"],
                vert_upstream_motor=kb_config["vert_upstream_motor"],
                vert_downstream_motor=kb_config["vert_downstream_motor"],
                # Bender motors
                horiz_upstream_bender=kb_config.get("horiz_upstream_bender", ""),
                horiz_downstream_bender=kb_config.get("horiz_downstream_bender", ""),
                vert_upstream_bender=kb_config.get("vert_upstream_bender", ""),
                vert_downstream_bender=kb_config.get("vert_downstream_bender", ""),
            )
            # Convert motors to fully qualified PV names (if not empty)
            motors = {
                key: f"{ioc_prefix}:{val}" for key, val in motors.items() if bool(val)
            }
        except KeyError as ex:
            raise exceptions.UnknownDeviceConfiguration(
                f"Device {name} missing '{ex.args[0]}': {kb_config}"
            )
        # Make the device
        devices.append(
            make_device(
                KBMirrors, prefix=prefix, name=name, labels={"kb_mirrors"}, **motors
            )
        )
    # Create single-bounce mirrors
    for name, mirror_config in config.get("mirrors", {}).items():
        # Decide which base class of mirror to use
        class_name = mirror_config["device_class"]
        if mirror_config.get("bendable", False):
            class_name = f"Bendable{class_name}"
        DeviceClass = globals().get(class_name)
        # Check that it's a valid device class
        if DeviceClass is None:
            msg = f"mirrors.{name}.device_class={mirror_config['device_class']}"
            raise exceptions.UnknownDeviceConfiguration(msg)
        devices.append(
            make_device(
                DeviceClass,
                prefix=mirror_config["prefix"],
                name=name,
                labels={"mirrors"},
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
