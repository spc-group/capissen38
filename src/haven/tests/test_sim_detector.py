import pytest

from ophyd import Signal
from ophyd.sim import instantiate_fake_device

from haven.devices import SimDetectorThreaded


@pytest.fixture()
def sim_det(sim_registry):
    sim_det = instantiate_fake_device(
        SimDetectorThreaded,
        prefix="255idSimDet:",
        name="sim_det"
    )
    return sim_det


def test_signals(sim_det):
    assert sim_det.drv.prefix == "255idSimDet:cam1:"
    assert type(sim_det.drv).acquire.suffix == "Acquire"
    assert type(sim_det.drv).detector_state.suffix == "DetectorState_RBV"
    assert type(sim_det.drv).acquire_busy.suffix == "AcquireBusy"
    assert type(sim_det.drv).gain.suffix == "Gain"
    assert type(sim_det.hdf).file_path.suffix == "FilePath"
    assert type(sim_det.hdf).file_name.suffix == "FileName"
