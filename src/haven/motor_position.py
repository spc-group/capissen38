import logging
import time
from datetime import datetime
from typing import Mapping, Sequence

import intake
from bluesky import plan_stubs as bps
from bluesky import plans as bp
from pydantic import BaseModel
from rich import print as rprint
from tiled.queries import Key, Regex

from .catalog import Catalog, tiled_client
from .instrument import beamline

log = logging.getLogger(__name__)


__all__ = [
    "save_motor_position",
    "list_motor_positions",
    "recall_motor_position",
    "list_current_motor_positions",
]


class MotorAxis(BaseModel):
    name: str
    readback: float
    offset: float | None = None

    def as_dict(self):
        return {"name": self.name, "readback": self.readback, "offset": self.offset}


class MotorPosition(BaseModel):
    name: str
    motors: Sequence[MotorAxis]
    uid: str | None = None
    savetime: float | None = None

    @classmethod
    def _load(Cls, run_md, data_keys, data):
        """Common routines for sync and async loading."""
        if run_md["start"]["plan_name"] != "save_motor_position":
            raise ValueError(f"Run {run_md['start']['uid']} is not a motor position.")
        # Extract motor positions from the run
        motor_axes = []
        for axis_name in data_keys:
            axis = MotorAxis(
                name=axis_name,
                readback=data[axis_name][0],
            )
            motor_axes.append(axis)
        # Create the motor position object
        return Cls(
            name=run_md["start"]["position_name"],
            motors=motor_axes,
            uid=run_md["start"]["uid"],
            savetime=run_md["start"]["time"],
        )

    @classmethod
    def load(Cls, run):
        """Create a new MotorPosition object from a Tiled Bluesky run."""
        data_keys = run["primary"].metadata["data_keys"]
        return Cls._load(
            run_md=run.metadata,
            # Assumes the 0-th descriptor is for the primary stream
            data_keys=data_keys,
            data=run["primary/internal/events"].read(),
        )

    @classmethod
    async def aload(Cls, scan):
        """Create a new MotorPosition object from a Tiled Bluesky run.
        Similar to ``MotorPosition.load()``, but asynchronous."""
        return Cls._load(
            run_md=await scan.metadata,
            data_keys=await scan.data_keys(),
            data=await scan.data(),
        )


def default_collection():
    catalog = intake.catalog.load_combo_catalog()["haven"]
    client = catalog._asset_registry_db.client
    collection = client.get_database().get_collection("motor_positions")
    return collection


# Prepare the motor positions
async def rbv(motor):
    """Helper function to get readback value (rbv)."""
    if hasattr(motor, "readback"):
        return await motor.readback.get_value()
    elif hasattr(motor, "user_readback"):
        return await motor.user_readback.get_value()
    else:
        return await motor.get_value()


def save_motor_position(*motors, name: str, md: Mapping = {}):
    """A Bluesky plan to Save the current positions of a number of motors.

    Parameters
    ==========
    *motors
      The list of motors (or motor names/labels) whose position to
      save.
    name
      A human-readable name for this position (e.g. "sample center")
    md
      Additional metadata to store with the motor position.

    """
    # Resolve device names or labels
    motors = [beamline.devices[motor] for motor in motors]
    # Create the new run object
    _md = {
        "position_name": name,
        "plan_name": "save_motor_position",
    }
    _md.update(md)
    yield from bp.count(motors, md=_md)


def print_motor_position(position):
    # Prepare metadata strings for the header
    metadata = []
    if position.uid is not None:
        metadata.append(f'uid="{position.uid}"')
    if position.savetime is not None:
        timestamp = datetime.fromtimestamp(position.savetime).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        ts_str = f"{timestamp}"
        metadata.append(ts_str)
    if len(metadata) > 0:
        metadata_str = f"{', '.join(metadata)}"
    else:
        metadata_str = ""
    # Write the output header
    outputs = [
        f"[bold]{position.name}[/]",
        f"┃ [italic dim]{metadata_str}[/]",
    ]
    # Write the motor positions
    for idx, motor in enumerate(position.motors):
        # Figure out some nice tree aesthetics
        is_last_motor = idx == (len(position.motors) - 1)
        box_char = "┗" if is_last_motor else "┣"
        outputs.append(
            f"{box_char}━[purple]{motor.name}[/]: "
            f"{motor.readback}, offset: {motor.offset}"
        )
    rprint("\n".join(outputs))


async def list_motor_positions(after: float | None = None, before: float | None = None):
    """Print a list of previously saved motor positions.

    The name and UID will be printed, along with each motor and it's
    position.

    before
      Only include motor positions recorded before this unix
      timestamp if provided.
    after
      Only include motor positions recorded after this unix
      timestamp if provided.

    """
    # Go through the results and display them
    were_found = False
    async for position in get_motor_positions(before=before, after=after):
        if were_found:
            # Add a blank line
            print("\n")
        else:
            were_found = True
        print_motor_position(position)
    # Some feedback in the case of empty motor positions
    if not were_found:
        rprint(f"[yellow]No motor positions found: {before=}, {after=}[/]")


def get_motor_position(uid: str) -> MotorPosition:
    """Retrieve a previously saved motor position from the database.

    Parameters
    ==========
    uid
      The universal identifier for the Bluesky run with motor position
      info.

    Returns
    =======
    position
      The most recent motor position with data retrieved from the
      database.

    """
    # Filter out query parameters that are ``None``
    client = tiled_client()
    run = client[uid]
    # Feedback for if no matching motor positions are in the database
    position = MotorPosition.load(run)
    return position


async def get_motor_positions(
    before: float | None = None,
    after: float | None = None,
    name: str | None = None,
    case_sensitive: bool = True,
) -> list[MotorPosition]:
    """Get all motor position objects from the catalog.

    Parameters
    ==========
    before
      Only include motor positions recorded before this unix
      timestamp if provided.
    after
      Only include motor positions recorded after this unix
      timestamp if provided.
    name
      A regular expression used to filter motor positions based on
      name.
    case_sensitive
      Whether the regular expression is applied with case-sensitivity.

    Returns
    =======
    positions
      The motor positions matching the requested parameters.

    """
    runs = Catalog(client=tiled_client())
    # Filter only saved motor positions
    runs = await runs.search(Key("plan_name") == "save_motor_position")
    # Filter by timestamp
    if before is not None:
        runs = await runs.search(Key("time") < before)
    if after is not None:
        runs = await runs.search(Key("time") > after)
    # Filter by position name
    if name is not None:
        runs = await runs.search(
            Regex("position_name", name, case_sensitive=case_sensitive)
        )
    # Create the actual motor position objects
    async for uid, run in runs.items():
        try:
            yield await MotorPosition.aload(run)
        except KeyError:
            continue


def recall_motor_position(uid: str):
    """Set motors to their previously saved positions.

    Parameters
    ==========
    uid
      The universal identifier for the the document in the collection.

    """
    # Get the saved position from the database
    position = get_motor_position(uid=uid)
    # Create a move plan to recall the position
    plan_args = []
    for axis in position.motors:
        motor = beamline.devices[axis.name]
        plan_args.append(motor)
        plan_args.append(axis.readback)
    yield from bps.mv(*plan_args)


async def list_current_motor_positions(*motors, name="Current motor positions"):
    """list and print the current positions of a number of motors

    Parameters
    ==========
    *motors
      The list of motors (or motor names/labels) whose position to
      save.
    name
      A human-readable name for this position (e.g. "sample center")

    """
    # Resolve device names or labels
    motors = [beamline.devices[m] for m in motors]
    # Build the list of motor positions
    motor_axes = []
    for m in motors:
        payload = dict(name=m.name, readback=await rbv(m))
        # Save the calibration offset for motors
        if hasattr(m, "user_offset"):
            payload["offset"] = await m.user_offset.get_value()
        axis = MotorAxis(**payload)
        motor_axes.append(axis)
    position = MotorPosition(
        name=name, motors=motor_axes, uid=None, savetime=time.time()
    )
    # Display the current motor positions
    print_motor_position(position)


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
