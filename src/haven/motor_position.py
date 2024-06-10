import logging
import time
from datetime import datetime
from typing import Optional, Sequence

import intake
import pymongo
from bluesky import plan_stubs as bps
from bson.objectid import ObjectId
from pydantic import BaseModel

from . import exceptions
from .instrument.instrument_registry import registry

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
    offset: Optional[float] = None

    def as_dict(self):
        return {"name": self.name, "readback": self.readback, "offset": self.offset}


class MotorPosition(BaseModel):
    name: str
    motors: Sequence[MotorAxis]
    uid: Optional[str] = None
    savetime: Optional[float] = None

    def save(self, collection):
        payload = {
            "name": self.name,
            "motors": [m.as_dict() for m in self.motors],
            "savetime": self.savetime,
        }
        item_id = collection.insert_one(payload).inserted_id
        return item_id

    @classmethod
    def load(Cls, document):
        # Create a MotorPosition object
        motor_axes = [
            MotorAxis(
                name=m["name"], readback=m["readback"], offset=m.get("offset", None)
            )
            for m in document["motors"]
        ]
        position = Cls(
            name=document["name"],
            motors=motor_axes,
            uid=str(document["_id"]),
            savetime=document.get("savetime"),
        )
        return position


def default_collection():
    catalog = intake.catalog.load_combo_catalog()["haven"]
    client = catalog._asset_registry_db.client
    collection = client.get_database().get_collection("motor_positions")
    return collection


# Prepare the motor positions
def rbv(motor):
    """Helper function to get readback value (rbv)."""
    try:
        # Wrap this in a try block because not every signal has this argument
        motor_data = motor.get(use_monitor=False)
    except TypeError:
        log.debug("Failed to do get() with ``use_monitor=False``")
        motor_data = motor.get()
    if hasattr(motor_data, "readback"):
        return motor_data.readback
    elif hasattr(motor_data, "user_readback"):
        return motor_data.user_readback
    else:
        return motor_data


def save_motor_position(*motors, name: str, collection=None):
    """Save the current positions of a number of motors to a database.

    Parameters
    ==========
    *motors
      The list of motors (or motor names/labels) whose position to
      save.
    name
      A human-readable name for this position (e.g. "sample center")
    collection
      A pymongo collection object to receive the data. Meant for
      testing.

    Returns
    =======
    item_id
      The ID of the item in the database.
    """
    # Get default collection if none was given
    if collection is None:
        collection = default_collection()
    # Resolve device names or labels
    motors = registry.findall(motors)
    # Prepare the motor positions
    motor_axes = []
    for m in motors:
        payload = dict(name=m.name, readback=rbv(m))
        # Save the calibration offset for motors
        if hasattr(m, "user_offset"):
            payload["offset"] = m.user_offset.get()
        axis = MotorAxis(**payload)
        motor_axes.append(axis)
    savetime = time.time()
    position = MotorPosition(name=name, motors=motor_axes, savetime=savetime)
    # Write to the database
    pos_id = position.save(collection=collection)
    log.info(f"Saved motor position {name} (uid={pos_id})")
    return pos_id


def print_motor_position(position):
    BOLD = "\033[1m"
    END = "\033[0m"
    # Prepare metadata strings for the header
    metadata = []
    if position.uid is not None:
        metadata.append(f'uid="{position.uid}"')
    if position.savetime is not None:
        timestamp = datetime.fromtimestamp(position.savetime).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        ts_str = f"timestamp={timestamp}"
        metadata.append(ts_str)
    if len(metadata) > 0:
        metadata_str = f" ({', '.join(metadata)})"
    else:
        metadata_str = ""
    # Write the output header
    output = f"\n{BOLD}{position.name}{END}{metadata_str}\n"
    # Write the motor positions
    for idx, motor in enumerate(position.motors):
        # Figure out some nice tree aesthetics
        is_last_motor = idx == (len(position.motors) - 1)
        box_char = "┗" if is_last_motor else "┣"
        output += f"{box_char}━{motor.name}: {motor.readback}, offset: {motor.offset}\n"
    print(output, end="")


def list_motor_positions(collection=None):
    """Print a list of saved motor positions.

    The name and UID will be printed, along with each motor and it's
    position.

    Parameters
    ==========
    collection
      The mongodb collection from which to print motor positions.

    """
    # Get default collection if none was given
    if collection is None:
        collection = default_collection()
    # Get the motor positions from disk
    results = collection.find()
    # Go through the results and display them
    were_found = False
    for doc in results:
        were_found = True
        position = MotorPosition.load(doc)
        print_motor_position(position)
    # Some feedback in the case of empty motor positions
    if not were_found:
        print(f"No motor positions found: {collection}")


def get_motor_position(
    uid: Optional[str] = None, name: Optional[str] = None, collection=None
) -> MotorPosition:
    """Retrieve a previously saved motor position from the database.

    Parameters
    ==========
    uid
      The universal identifier for the the document in the collection.
    name
      The name of the saved motor position, as given with the *name*
      parameter to the ``save_motor_position`` function.
    collection
      The mongodb collection from which to print motor positions.

    Returns
    =======
    position
      The most recent motor position with data retrieved from the
      database.

    """
    # Check that at least one of the parameters is given
    has_query_param = any([val is not None for val in [uid, name]])
    if not has_query_param:
        raise TypeError("At least one query parameter (*uid*, *name*) is required")
    # Get default collection if none was given
    if collection is None:
        collection = default_collection()
    # Build query for finding motor positions
    if uid is not None:
        _id = ObjectId(uid)
    else:
        _id = None
    query_params = {"_id": _id, "name": name}
    # Filter out query parameters that are ``None``
    query_params = {k: v for k, v in query_params.items() if v is not None}
    result = collection.find_one(query_params, sort=[("savetime", pymongo.DESCENDING)])
    # Feedback for if no matching motor positions are in the database
    if result is None:
        raise exceptions.DocumentNotFound(
            f'Could not find document matching: {query_params}"'
        )
    position = MotorPosition.load(result)
    return position


def recall_motor_position(
    uid: Optional[str] = None, name: Optional[str] = None, collection=None
):
    """Set motors to their previously saved positions.

    Parameters
    ==========
    uid
      The universal identifier for the the document in the collection.
    name
      The name of the saved motor position, as given with the *name*
      parameter to the ``save_motor_position`` function.
    collection
      The mongodb collection from which to print motor positions.

    """
    # Get default collection if none was given
    if collection is None:
        collection = default_collection()
    # Get the saved position from the database
    position = get_motor_position(uid=uid, name=name, collection=collection)
    # Create a move plan to recall the position
    plan_args = []
    for axis in position.motors:
        motor = registry.find(name=axis.name)
        plan_args.append(motor)
        plan_args.append(axis.readback)
    yield from bps.mv(*plan_args)


def list_current_motor_positions(*motors, name="current motor"):
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
    motors = [registry.find(name=m) for m in motors]
    # Build the list of motor positions
    motor_axes = []
    for m in motors:
        payload = dict(name=m.name, readback=rbv(m))
        # Save the calibration offset for motors
        if hasattr(m, "user_offset"):
            payload["offset"] = m.user_offset.get()
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
