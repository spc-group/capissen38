from apstools.synApps import TransformRecord
from ophyd import Component as Cpt
from ophyd import Device, Kind, OphydObject

from .. import exceptions
from .._iconfig import load_config
from .device import make_device
from .motor import HavenMotor


class Table(Device):
    """A dynamic Ophyd device for an optical table.

    This device will have the components needed for the configuration
    of motors provided. For example, if *horizontal_motor* is
    provided, then the device will have a ``horizontal`` attribute
    that is the corresponding horizontal motor.

    There are several dynamic parameters when creating an object that
    control the structure of the resulting device. These are described
    individually below and are assumed relative to *prefix*. If
    *upstream_motor* and *downstream_motor* are not empty, then
    *vertical* and *pitch* will point to a pseudo motor who's PV is
    determined by *pseudo_motors* (the value of *vertical_motor* will
    be ignored in this case). For example:

    .. code:: python

        tbl = Table(
            "255idcVME:",
            pseudo_motors="table_us:",
            transforms="table_us_trans:",
            upstream_motor="m3",
            downstream_motor="m4",
            name="my_table",
        )

    will produce a table with the following components:

    - *upstream*: "255idcVME:m3"
    - *downstream*: "255idcVME:m4"
    - *vertical*: "255idcVME:table_us:height"
    - *pitch*: "255idcVME:table_us:pitch"
    - *drive*: transform "255idcVME:table_us_trans:Drive"
    - *readback*: transform "255idcVME:table_us_trans:Readback"

    Parameters
    ==========
    prefix
      The PV prefix common to all components. E.g. "25idcVME:".
    vertical_motor
      The suffix for the real motor controlling the height of the
      table (e.g. "m1"). Ignored if *upstream_motor* and
      *downstream_motor* are provided.
    horizontal_motor
      The suffix for the real motor controlling the lateral movement
      of the table (e.g. "m1").
    upstream_motor
      The suffix for the real motor controlling the height of the
      upstream leg of the table (e.g. "m1").
    downstream_motor
      The suffix for the real motor controlling the height of the
      downstream leg of the table (e.g. "m1").
    pseudo_motors
      The suffix for the pseudo motors controlling the orientation of
      the table. E.g. "table_ds:". Creates the components: *height*
      and *pitch*.
    transforms
      The suffix for the pseudo motor transform records
      (e.g. "table_ds_trans:"). Creates the components:
      *vertical_drive_transform" and "vertical_readback_transform".

    """

    # These are the possible components that could be present
    vertical: OphydObject
    horizontal: OphydObject
    upstream: OphydObject
    downstream: OphydObject
    pitch: OphydObject
    horizontal_drive_transform: OphydObject
    horizontal_readback_transform: OphydObject

    def __new__(
        cls,
        prefix,
        *args,
        vertical_motor: str = "",
        horizontal_motor: str = "",
        upstream_motor: str = "",
        downstream_motor: str = "",
        pseudo_motors: str = "",
        transforms: str = "",
        **kwargs,
    ):
        # See if we have direct control over the vertical/horizontal positions
        comps = {}
        if bool(vertical_motor):
            comps["vertical"] = Cpt(
                HavenMotor,
                vertical_motor,
                labels={"motors"},
            )
        if bool(horizontal_motor):
            comps["horizontal"] = Cpt(
                HavenMotor,
                horizontal_motor,
                labels={"motors"},
            )
        if bool(upstream_motor):
            comps["upstream"] = Cpt(
                HavenMotor,
                upstream_motor,
                labels={"motors"},
            )
        if bool(downstream_motor):
            comps["downstream"] = Cpt(
                HavenMotor,
                downstream_motor,
                labels={"motors"},
            )
        # Check if we need to add the pseudo motors and tranforms
        if bool(upstream_motor) and bool(downstream_motor):
            comps["vertical"] = Cpt(
                HavenMotor, f"{pseudo_motors}height", labels={"motors"}
            )
            comps["pitch"] = Cpt(HavenMotor, f"{pseudo_motors}pitch", labels={"motors"})
            comps["vertical_drive_transform"] = Cpt(
                TransformRecord, f"{transforms}Drive", kind=Kind.config
            )
            comps["vertical_readback_transform"] = Cpt(
                TransformRecord, f"{transforms}Readback", kind=Kind.config
            )
        # Now create a customized class for all the motors given
        new_cls = type("Table", (cls,), comps)
        return object.__new__(new_cls)

    def __init__(
        self,
        *args,
        pseudo_motors: str = "",
        transforms: str = "",
        vertical_motor: str = "",
        horizontal_motor: str = "",
        upstream_motor: str = "",
        downstream_motor: str = "",
        **kwargs,
    ):
        # __init__ needs to accept the arguments accepted by __new__.
        self.pseudo_motors = pseudo_motors
        self.transforms = transforms
        super().__init__(*args, **kwargs)


def load_tables(config=None):
    if config is None:
        config = load_config()
    # Create two-bounce KB mirror sets
    devices = []
    for name, tbl_config in config.get("table", {}).items():
        # Build the motor prefixes
        try:
            prefix = tbl_config["prefix"]
            attr_names = [
                "upstream_motor",
                "downstream_motor",
                "horizontal_motor",
                "vertical_motor",
                "transforms",
                "pseudo_motors",
            ]
            attrs = {attr: tbl_config.get(attr, "") for attr in attr_names}
        except KeyError as ex:
            raise exceptions.UnknownDeviceConfiguration(
                f"Device {name} missing '{ex.args[0]}': {tbl_config}"
            ) from ex
        # Make the device
        devices.append(
            make_device(
                Table,
                prefix=prefix,
                name=name,
                labels={"tables"},
                **attrs,
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
