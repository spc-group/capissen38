import pytest

from ophyd import Signal
from ophyd.sim import instantiate_fake_device

from haven.devices import SimDetectorThreaded, SimDetector


@pytest.fixture()
async def sim_det(sim_registry):
    det = SimDetector(name="sim_det", prefix="255idSimDet:")
    await det.connect(mock=True)
    return det


def test_signals(sim_det):
    assert sim_det.drv.acquire.source == "mock+ca://255idSimDet:cam1:Acquire_RBV"
    assert sim_det.drv.acquire_time.source == "mock+ca://255idSimDet:cam1:AcquireTime_RBV"
    assert sim_det.drv.detector_state.source == "mock+ca://255idSimDet:cam1:DetectorState_RBV"
    # assert sim_det.drv.gain.source == "mock+ca://255idSimDet:cam1:Gain"
    assert sim_det.hdf.file_path.source == "mock+ca://255idSimDet:HDF1:FilePath_RBV"
    assert sim_det.hdf.file_name.source == "mock+ca://255idSimDet:HDF1:FileName_RBV"
    # Overlays for showing annotations on-screen only
    assert sim_det.overlays[0].shape.source == "mock+ca://255idSimDet:Over1:1:Shape_RBV"
    assert sim_det.overlays[0].center_x.source == "mock+ca://255idSimDet:Over1:1:CenterX_RBV"
    assert sim_det.overlays[0].center_y.source == "mock+ca://255idSimDet:Over1:1:CenterY_RBV"
    assert sim_det.overlays[0].size_x.source == "mock+ca://255idSimDet:Over1:1:SizeX_RBV"
    assert sim_det.overlays[0].size_y.source == "mock+ca://255idSimDet:Over1:1:SizeY_RBV"
