import asyncio
import logging
from typing import Optional

from aioca import caget
from ophyd import Component as Cpt
from ophyd import EpicsMotor, EpicsSignal, EpicsSignalRO

from .._iconfig import load_config
from .device import aload_devices, make_device
from .instrument_registry import registry

log = logging.getLogger(__name__)


class HavenMotor(EpicsMotor):
    """The default motor for haven movement.

    Returns to the previous value when being unstaged.
    """

    description = Cpt(EpicsSignal, ".DESC", kind="omitted")
    tweak_value = Cpt(EpicsSignal, ".TWV", kind="omitted")
    tweak_forward = Cpt(EpicsSignal, ".TWF", kind="omitted", tolerance=2)
    tweak_reverse = Cpt(EpicsSignal, ".TWR", kind="omitted", tolerance=2)
    motor_stop = Cpt(EpicsSignal, ".STOP", kind="omitted", tolerance=2)
    soft_limit_violation = Cpt(EpicsSignalRO, ".LVIO", kind="omitted")

    def stage(self):
        super().stage()
        # Save starting position to restore later
        self._old_value = self.user_readback.value

    def unstage(self):
        super().unstage()
        # Restore the previously saved position after the scan ends
        self.set(self._old_value, wait=True)


def load_all_motor_coros(config=None):
    if config is None:
        config = load_config()
    # Figure out the prefix
    coros = []
    for name, config in config["motor"].items():
        prefix = config["prefix"]
        num_motors = config["num_motors"]
        log.info(f"Loading {num_motors} motors from IOC: {name} ({prefix})")
        coros.extend(
            load_ioc_motor_coros(prefix=prefix, num_motors=num_motors, ioc_name=name)
        )
    return coros


def load_ioc_motor_coros(
    prefix: str, num_motors: int, ioc_name: Optional[str] = None
) -> list:
    """Create co-routines for loading IOC motors.

    These co-routines can then be run asynchronously by the caller
    with e.g. asyncio.gather()

    Parameters
    ==========
    prefix
      The IOC prefix for these motors
    num_motors
      How many motor records are in the IOC.
    ioc_name
      An extra ophyd device label for all motors in this IOC.

    Returns
    =======
    coros
      A list of tasks that can be awaited.

    """
    # Co-routines for creating motor objects
    for motor_num in range(num_motors):
        log.debug(f"Making coro for {prefix}, {motor_num}")
        yield load_motor(prefix, motor_num, ioc_name)


async def load_motor(prefix: str, motor_num: int, ioc_name: str = None):
    """Create the requested motor if it is reachable."""
    pv = f"{prefix}:m{motor_num+1}"
    # Check that we're not duplicating a motor somewhere else (e.g. KB mirrors)
    existing_pvs = [m.prefix for m in registry.findall(label="motors", allow_none=True)]
    if pv in existing_pvs:
        log.info(f"Motor for prefix {pv} already exists. Skipping.")
        return
    # Get motor names
    config = load_config()
    # Get the motor name from the description PV
    try:
        name = await caget(f"{pv}.DESC")
    except asyncio.exceptions.TimeoutError:
        if not config["beamline"]["is_connected"]:
            # Beamline is not connected, so just use a generic name
            name = f"{prefix}_m{motor_num+1}"
        else:
            # Motor is unreachable, so skip it
            log.warning(f"Could not connect to motor: {pv}")
            return
    else:
        log.debug(f"Resolved motor {pv} to '{name}'")

    # Create the motor device
    unused_motor_names = [f"motor {motor_num+1}", ""]
    if name in unused_motor_names:
        # It's an unnamed motor, so skip it
        log.info(f"SKipping unnamed motor {pv}")
    else:
        # Create a new motor object
        labels = {"motors", "extra_motors", "baseline"}
        if ioc_name is not None:
            labels = set([ioc_name, *labels])
        return await make_device(HavenMotor, prefix=pv, name=name, labels=labels)


def load_all_motors(config=None):
    return asyncio.run(aload_devices(*load_all_motor_coros(config=config)))


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
