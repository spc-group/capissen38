import logging

from ophyd import Component as Cpt
from ophyd import Device
from ophyd import DynamicDeviceComponent as DCpt
from ophyd import EpicsMotor, EpicsSignal, EpicsSignalRO

from .._iconfig import load_config
from .device import make_device

log = logging.getLogger(__name__)


LOAD_TIMEOUT = 40


class Sample(Device):
    """An individual robot sample that can be loaded.

    Signals
    =======
    present
      Whether or not a sample is physically present on the stage.
    empty
      Whether or not no sample is physically present on the stage.
    load
      Direct the robot to physically move this sample to the loading
      position. Can be slow (~25-30 seconds).
    unload
      Direct the robot to physically remove this sample to the loading
      position. Can be slow (~25-30 seconds).
    x
      The x position of the robot in Cartesian coordinates.
    y
      The y position of the robot in Cartesian coordinates.
    z
      The z position of the robot in Cartesian coordinates.
    rx
      The rx position of the robot in Cartesian coordinates.
    ry
      The ry position of the robot in Cartesian coordinates.
    rz
      The position of the robot in Cartesian coordinates.

    """

    present = Cpt(EpicsSignalRO, ":present")
    empty = Cpt(EpicsSignalRO, ":empty")
    load = Cpt(
        EpicsSignal,
        ":load",
        kind="omitted",
        write_timeout=LOAD_TIMEOUT,
        put_complete=True,
    )
    unload = Cpt(
        EpicsSignal,
        ":unload",
        kind="omitted",
        write_timeout=LOAD_TIMEOUT,
        put_complete=True,
    )
    x = Cpt(EpicsSignalRO, ":x")
    y = Cpt(EpicsSignalRO, ":y")
    z = Cpt(EpicsSignalRO, ":z")
    rx = Cpt(EpicsSignalRO, ":rx")
    ry = Cpt(EpicsSignalRO, ":ry")
    rz = Cpt(EpicsSignalRO, ":rz")


def transfer_samples(num_samples: int):
    """Create a dictionary with robot sample device definitions.
    For use with an ophyd DynamicDeviceComponent.
    Parameters
    ==========
    num_dios
      How many samples to create.
    """
    samples = {}
    # Now the sample holder bases are only located at sites [8,9,10,14,15,16,20,21,22] on the board.
    for n in [8, 9, 10, 14, 15, 16, 20, 21, 22]:  # range(num_samples):
        samples[f"sample{n}"] = (Sample, f":sample{n}", {})
    return samples


class Robot(Device):
    # joints and position
    i = Cpt(EpicsMotor, ":i")
    j = Cpt(EpicsMotor, ":j")
    k = Cpt(EpicsMotor, ":k")
    l = Cpt(EpicsMotor, ":l")
    m = Cpt(EpicsMotor, ":m")
    n = Cpt(EpicsMotor, ":n")
    x = Cpt(EpicsMotor, ":x")
    y = Cpt(EpicsMotor, ":y")
    z = Cpt(EpicsMotor, ":z")
    rx = Cpt(EpicsMotor, ":rx")
    ry = Cpt(EpicsMotor, ":ry")
    rz = Cpt(EpicsMotor, ":rz")
    acc = Cpt(EpicsSignal, ":acceleration", kind="config")
    vel = Cpt(EpicsSignal, ":velocity", kind="config")

    # dashboard
    remote_control = Cpt(EpicsSignalRO, ":dashboard:remote_control", kind="config")
    program = Cpt(EpicsSignal, ":dashboard:program_rbv", kind="omitted")
    program_rbv = Cpt(EpicsSignalRO, ":dashboard:program_rbv", kind="config")
    installation = Cpt(EpicsSignal, ":dashboard:installation", kind="config")
    playRbt = Cpt(EpicsSignal, ":dashboard:play", kind="omitted")
    stopRbt = Cpt(EpicsSignal, ":dashboard:stop", kind="omitted")
    pauseRbt = Cpt(EpicsSignal, ":dashboard:pause", kind="omitted")
    quitRbt = Cpt(EpicsSignal, ":dashboard:quit", kind="omitted")
    shutdown = Cpt(EpicsSignal, ":dashboard:shutdown", kind="omitted")
    release_brake = Cpt(EpicsSignal, ":dashboard:release_brake", kind="omitted")
    close_safety_popup = Cpt(
        EpicsSignal, ":dashboard:close_safety_popup", kind="config"
    )
    unlock_protective_stop = Cpt(
        EpicsSignal, ":dashboard:unlock_protective_stop", kind="config"
    )
    restart_safety = Cpt(EpicsSignal, ":dashboard:restart_safety", kind="config")
    program_running = Cpt(EpicsSignal, ":dashboard:program_running", kind="config")
    safety_status = Cpt(EpicsSignal, ":dashboard:safety_status", kind="config")
    power = Cpt(EpicsSignal, ":dashboard:power", kind="omitted")
    power_rbv = Cpt(EpicsSignalRO, ":dashboard:power_rbv", kind="config")

    # gripper
    gripper_activate = Cpt(EpicsSignal, ":gripper.ACT", kind="omitted")
    gripper_activated = Cpt(EpicsSignal, ":gripper.ACR", kind="config")
    gripper_close = Cpt(EpicsSignal, ":gripper.CLS", kind="omitted")
    gripper_open = Cpt(EpicsSignal, ":gripper.OPN", kind="omitted")
    gripper_rbv = Cpt(EpicsSignal, ":gripper.RBV")
    gripper_val = Cpt(EpicsSignal, ":gripper.VAL")
    gripper_force = Cpt(EpicsSignal, ":gripper.FRC", kind="config")

    # busy
    busy = Cpt(EpicsSignal, ":busy", kind="omitted")

    # sample transfer
    current_sample = Cpt(EpicsSignalRO, ":current_sample", kind="config")
    unload_current_sample = Cpt(
        EpicsSignal,
        ":unload_current_sample",
        kind="omitted",
        write_timeout=LOAD_TIMEOUT,
        put_complete=True,
    )
    current_sample_reset = Cpt(EpicsSignal, ":current_sample_reset", kind="omitted")
    home = Cpt(EpicsSignal, ":home", kind="config")
    cal_stage = Cpt(EpicsSignal, ":cal_stage", kind="config")

    samples = DCpt(transfer_samples(24))


def load_robots(config=None):
    # Load PV's from config
    if config is None:
        config = load_config()
    # Build robot devices
    robots = config.get("robot", {})
    devices = []
    for name, cfg in robots.items():
        devices.append(
            make_device(Robot, name=name, labels={"robots"}, prefix=cfg["prefix"])
        )
    return devices


# -----------------------------------------------------------------------------
# :author:    Yanna Chen
# :email:     yannachen@anl.gov
# :copyright: Copyright © 2024, UChicago Argonne, LLC
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
