import logging

from bluesky import plan_stubs as bps

from ..instrument.instrument_registry import registry
from ..motor_position import rbv

log = logging.getLogger(__name__)


__all__ = ["robot_transfer_sample"]


ON = 1


def robot_transfer_sample(robot, sampleN, *args):
    """
    Use robot to load sampleN at a fixed Aerotech stage position or any
    motors.

    e.g.
    Load sample:
    robot_sample(robot, 9, motor1, 100, motor2, 200, motor3, 50)

    Unload sample:
    robot_sample(robot, None, motor1, 100, motor2, 200, motor3, 50)

    Parameters:
    - robot: robot device
    - sampleN: Sample number
    - *args: multiple pairs of motor and pos
    """

    robot = registry.find(robot)

    # Check if power is on
    # if robot.power_rbv.get() == Off:
    #    raise ValueError("Robot is NOT powered. Please turn on the power.")

    # Check if remote control is on
    # if not robot.remote_control.get() == Off:
    #    raise ValueError(
    #        "Robot is NOT in reomete control mode. Please click on Pad for remote control."
    #    )

    # Check if gripper is on
    # if robot.gripper_activated.get() == Off:
    #    raise ValueError("Gripper is not activated. Please activate the gripper.")

    # Check if robot is running
    # if robot.grogram_running.get() == On:
    #   raise ValueError("Robot is running now.")

    # Find motors
    motor_list = [registry.find(motor) for motor in args[::2]]
    new_positions = [pos for pos in args[1::2]]
    # Record the motor positions before load sampls
    initial_positions = [rbv(motor) for motor in motor_list]

    # Move the aerotech to the loading position
    for motor, pos in zip(motor_list, new_positions):
        yield from bps.mv(motor, pos)

    if sampleN == None:
        # Unload sample
        yield from bps.mv(robot.unload_current_sample, ON)

    else:
        # Load sampleN after all the other motor arrive at (pos1, pos2, pos3...)
        sample = getattr(
            robot.samples, f"sample{sampleN}"
        )  # Access the Sample device corresponding to sampleN
        print(sample.load)
        yield from bps.mv(sample.load, ON)  # Assuming '1' initiates the loading action

    # Return to the initial position
    for motor, pos in zip(motor_list[-1::-1], initial_positions[-1::-1]):
        yield from bps.mv(motor, pos)


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
