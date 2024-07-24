import pytest

from ophyd import EpicsMotor, sim
from ophyd_async.epics.motor import Motor

from haven.instrument.device import make_device, connect_devices
from haven.instrument.load_instrument import load_simulated_devices
from haven.instrument.motor import HavenMotor


@pytest.mark.asyncio
async def test_connect_devices():
    motor = Motor("255idc:m1", name="motor")
    new_motors = await connect_devices([motor], mock=True)
    assert len(new_motors) == 1
    assert new_motors[0] is motor


@pytest.mark.asyncio
async def test_connect_devices_with_registry(sim_registry):
    motor = Motor("255idc:m1", name="motor")
    await connect_devices([motor], mock=True, labels={"motors"}, registry=sim_registry)
    # Check that we can find our devices in the registry
    sim_registry.find(name="motor")
    sim_registry.find(label="motors")


def test_load_simulated_devices(sim_registry):
    load_simulated_devices()
    # Check motors
    sim_registry.find(name="sim_motor")
    # Check detectors
    sim_registry.find(name="sim_detector")


def test_load_fake_device(sim_registry):
    """Does ``make_device`` create a fake device if beamline is disconnected?"""
    motor = make_device(HavenMotor, name="real_motor")
    assert isinstance(motor.user_readback, sim.SynSignal)


def test_accept_fake_device(sim_registry):
    """Does ``make_device`` use a specific fake device if beamline is disconnected?"""
    FakeMotor = sim.make_fake_device(EpicsMotor)
    motor = make_device(HavenMotor, name="real_motor", FakeDeviceClass=FakeMotor)
    assert isinstance(motor, FakeMotor)


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
