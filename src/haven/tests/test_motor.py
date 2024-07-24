import pytest

from ophyd_async.core import DeviceCollector
from ophyd_async.epics.signal import epics_signal_r, epics_signal_rw, epics_signal_x


from haven.instrument import motor


@pytest.fixture()
def mocked_device_names(mocker):
    # Mock the caget calls used to get the motor name
    async def resolve_device_names(defns):
        for defn, name in zip(defns, ["SLT V Upper", "SLT V Lower", "SLT H Inbound"]):
            defn["name"] = name

    mocker.patch(
        "haven.instrument.motor.resolve_device_names", new=resolve_device_names
    )


@pytest.mark.asyncio
async def test_load_vme_motors(sim_registry, mocked_device_names):
    # Load the Ophyd motor definitions
    await motor.load_motors(registry=sim_registry)
    # Were the motors imported correctly
    motors = list(sim_registry.findall(label="motors"))
    assert len(motors) == 3
    # assert type(motors[0]) is motor.HavenMotor
    motor_names = [m.name for m in motors]
    assert "SLT_V_Upper" in motor_names
    assert "SLT_V_Lower" in motor_names
    assert "SLT_H_Inbound" in motor_names
    # # Check that the IOC name is set in labels
    # motor1 = sim_registry.find(name="SLT_V_Upper")
    # assert "VME_crate" in motor1._ophyd_labels_


@pytest.mark.skip(reason="Needs to be figured out with ophyd_async")
@pytest.mark.asyncio
async def test_skip_existing_motors(sim_registry, mocked_device_names):
    """If a motor already exists from another device, don't add it to the
    motors group.

    """
    # Create an existing fake motor
    m1 = motor.HavenMotor(
        "255idVME:m1", name="kb_mirrors_horiz_upstream",
    )
    # Load the Ophyd motor definitions
    await motor.load_motors(registry=sim_registry)
    # Were the motors imported correctly
    motors = list(sim_registry.findall(label="motors"))
    m = motors[0]
    assert len(motors) == 3
    motor_names = [m.name for m in motors]
    assert "kb_mirrors_horiz_upstream" in motor_names
    assert "SLT_V_Upper" in motor_names
    assert "SLT_V_Lower" in motor_names
    # Check that the IOC name is set in labels
    motor1 = sim_registry.find(name="SLT_V_Upper")
    assert "VME_crate" in motor1._ophyd_labels_


@pytest.mark.asyncio
async def test_motor_signals():
    # Prepare the motor device
    m = motor.HavenMotor("motor_ioc", name="test_motor")
    await m.connect(mock=True)
    description = await m.describe()
    assert hasattr(m, 'description')
    assert hasattr(m, "tweak_value")
    assert hasattr(m, "tweak_forward")
    assert hasattr(m, "tweak_reverse")
    assert hasattr(m, "soft_limit_violation")


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
