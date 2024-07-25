import pytest
from ophyd import DetectorBase
from ophyd_async.core import StandardDetector

from haven import load_config, registry
from haven.instrument.camera import AravisDetector, load_cameras
from haven.instrument.device import connect_devices

PREFIX = "255idgigeA:"


@pytest.fixture()
async def camera(sim_registry):
    camera = AravisDetector(prefix=PREFIX, name="s255id-gige-A")
    await camera.connect(mock=True)
    sim_registry.register(camera, labels={"cameras", "detectors"})
    # Registry with the simulated registry
    return camera

@pytest.mark.asyncio
async def test_load_cameras(sim_registry):
    await load_cameras(config=load_config())
    # Check that cameras were registered
    cameras = list(registry.findall(label="cameras"))
    assert len(cameras) == 1
    assert isinstance(cameras[0], StandardDetector)


def test_camera_device():
    camera = AravisDetector(PREFIX, name="camera")
    assert isinstance(camera, StandardDetector)


@pytest.mark.asyncio
async def test_camera_trigger_source_choices(camera):
    """Confirm the camera device has the right signals.

    Solves this inital error received when using detaul AravisDetector.

    > drv: NotConnected:
    >     trigger_source: TypeError: 25idcARV4:cam1:TriggerSource_RBV has choices ('Software', 'Line1', 'Line3', 'Action1'), which is not a superset of SubsetEnum['Freerun', 'Line1'].
    >     data_type: NotConnected: ca://25idcARV4:cam1:NDDataType_RBV
    > hdf: NotConnected:
    >     data_type: NotConnected: ca://25idcARV4:HDF1:NDDataType_RBV
    
    """
    desc = await camera.drv.trigger_source.describe()
    choices = desc['s255id-gige-A-drv-trigger_source']['choices']
    assert "Software" in choices
    assert "Line1" in choices


@pytest.mark.asyncio
async def test_camera_signals(camera):
    """Confirm the camera device has the right signals.

    Solves this inital error received when using detaul AravisDetector.

    > drv: NotConnected:
    >     trigger_source: TypeError: 25idcARV4:cam1:TriggerSource_RBV has choices ('Software', 'Line1', 'Line3', 'Action1'), which is not a superset of SubsetEnum['Freerun', 'Line1'].
    >     data_type: NotConnected: ca://25idcARV4:cam1:NDDataType_RBV
    > hdf: NotConnected:
    >     data_type: NotConnected: ca://25idcARV4:HDF1:NDDataType_RBV
    
    """
    desc = await camera.drv.data_type.describe()
    cam_source = desc['s255id-gige-A-drv-data_type']['source']
    assert cam_source == "mock+ca://255idgigeA:cam1:DataType_RBV"
    # Check HDF signal source
    desc = await camera.hdf.data_type.describe()
    hdf_source = desc['s255id-gige-A-hdf-data_type']['source']
    assert hdf_source == "mock+ca://255idgigeA:HDF1:DataType_RBV"
    


@pytest.mark.skip(reason="Deprecated with ophyd async")
def test_camera_in_registry(sim_registry):
    camera = AravisDetector(PREFIX, name="camera")
    # Check that all sub-components are accessible
    camera = sim_registry.find(camera.name)
    sim_registry.find(f"{camera.name}_cam")
    sim_registry.find(f"{camera.name}_cam.gain")


def test_default_time_signal(camera):
    assert camera.default_time_signal is sim_camera.cam.acquire_time


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
