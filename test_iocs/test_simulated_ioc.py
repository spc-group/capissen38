import logging
import time
from pathlib import Path

import pytest
from epics import caget, caput

log = logging.getLogger(__name__)


ioc_dir = Path(__file__).parent.resolve() / "iocs"


@pytest.mark.skip(reason="Simulated IOCs are deprecated.")
def test_simulated_ioc(ioc_simple):
    assert caget(ioc_simple.pvs["B"], use_monitor=False) == 2.0
    caput(ioc_simple.pvs["B"], 5)
    time.sleep(0.1)
    assert caget(ioc_simple.pvs["B"], use_monitor=False) == 5


@pytest.mark.skip(reason="Simulated IOCs are deprecated.")
def test_motor_ioc(ioc_motor):
    prefix = "255idVME:"
    # Check that the starting value is different than what we'll set it to
    assert caput(f"{prefix}m1", 1000)
    assert caget(f"{prefix}m1", use_monitor=False) != pytest.approx(4000)
    # Change the value
    caput(f"{prefix}m1", 4000.0)
    time.sleep(1)
    # Check that the record got updated
    assert caget(f"{prefix}m1.VAL", use_monitor=False) == 4000.0
    assert caget(f"{prefix}m1.RBV", use_monitor=False) == 4000.0


@pytest.mark.skip(reason="Simulated IOCs are deprecated.")
def test_scaler_ioc(ioc_scaler):
    # Check that all the channels have the right counts
    for ch_num in range(1, 32):
        pv = f"255idVME:scaler1.S{ch_num}"
        assert caget(pv) is not None, pv


@pytest.mark.skip(reason="Simulated IOCs are deprecated.")
def test_mono_ioc(ioc_mono):
    # Test a regular motor
    caput("255idMono:ACS:m1", 0)
    caput("255idMono:ACS:m1.VAL", 0)
    assert caget("255idMono:ACS:m1", use_monitor=False) == 0.0
    assert caget("255idMono:ACS:m1.VAL", use_monitor=False) == 0.0
    # Change the value
    caput("255idMono:ACS:m1", 4000.0)
    time.sleep(0.1)
    # Check that the record got updated
    assert caget("255idMono:ACS:m1", use_monitor=False) == 4000.0
    assert caget("255idMono:ACS:m1.VAL", use_monitor=False) == 4000.0
    assert caget("255idMono:ACS:m1.RBV", use_monitor=False) == 4000.0
    # Test the energy motor
    caput("255idMono:Energy", 10000.0)
    time.sleep(0.1)
    assert caget("255idMono:Energy", use_monitor=False) == 10000.0
    # Change the value
    caput("255idMono:Energy", 6000.0)
    time.sleep(0.1)
    # Check that the record got updated
    assert caget("255idMono:Energy.VAL", use_monitor=False) == 6000.0
    assert caget("255idMono:Energy.RBV", use_monitor=False) == 6000.0


# @pytest.mark.skipif(
#     True or os.environ.get("GITHUB_ACTIONS", "false") == "true",
#     reason="Caproto is too slow on CI.",
# )
# def test_ioc_timing():
#     """Check that the IOC's don't take too long to load."""
#     # Launch the IOC numerous times to see how reproducible it is
#     for pass_num in range(5):
#         start = time.time()
#         with simulated_ioc(fp=ioc_dir / "simple.py"):
#             caput("simple:A", 100)
#             new_value = caget("simple:A", use_monitor=False)
#         assert new_value == 100.0
#         log.info(f"Finish pass {pass_num} in {time.time() - start} seconds.")
#         pass_time = time.time() - start
#         msg = f"Pass {pass_num} took {pass_time} seconds."
#         assert pass_time < 4, msg


@pytest.mark.skip(reason="Simulated IOCs are deprecated.")
def test_undulator_ioc(ioc_undulator):
    val = caget(ioc_undulator.pvs["energy"], use_monitor=False)
    assert val == 0.0


# def test_mono_undulator_ioc_again(ioc_undulator):
#     """Check that both mono and undulator IOC's can load in a second set
#     of tests.

#     This is in response to a specific test bug where this would fail.

#     """
#     pass


# def test_mono_undulator_ioc_a_third_time(ioc_undulator):
#     """Check that both mono and undulator IOC's can load in a second set
#     of tests.

#     This is in response to a specific test bug where this would fail.

#     """
#     pass


@pytest.mark.skip(reason="Simulated IOCs are deprecated.")
@pytest.mark.xfail
def test_bss_ioc(ioc_bss):
    caput(ioc_bss.pvs["esaf_cycle"], "2023-2", wait=True)
    val = caget(ioc_bss.pvs["esaf_cycle"], as_string=True, use_monitor=False)
    assert val == "2023-2"


@pytest.mark.skip(reason="Simulated IOCs are deprecated.")
def test_preamp_ioc(ioc_preamp):
    # Update PVs to recover from other tests
    caput(ioc_preamp.pvs["preamp1_sens_num"], "5")
    caput(ioc_preamp.pvs["preamp1_sens_unit"], "nA/V")
    caput(ioc_preamp.pvs["preamp4_sens_num"], "5")
    caput(ioc_preamp.pvs["preamp4_sens_unit"], "nA/V")
    # Check that the values were set
    assert caget(ioc_preamp.pvs["preamp1_sens_num"], use_monitor=False) == 2
    assert (
        caget(ioc_preamp.pvs["preamp1_sens_num"], use_monitor=False, as_string=True)
        == "5"
    )
    assert (
        caget(ioc_preamp.pvs["preamp4_sens_num"], use_monitor=False, as_string=True)
        == "5"
    )
    assert (
        caget(ioc_preamp.pvs["preamp1_sens_unit"], use_monitor=False, as_string=True)
        == "nA/V"
    )
    assert (
        caget(ioc_preamp.pvs["preamp4_sens_unit"], use_monitor=False, as_string=True)
        == "nA/V"
    )


@pytest.mark.skip(reason="Simulated IOCs are deprecated.")
def test_ptc10_ioc(ioc_ptc10):
    assert caput(ioc_ptc10.pvs["tc1_temperature"], 21.3)
    # Check that the values were set
    assert caget(ioc_ptc10.pvs["pid1_voltage"], use_monitor=False) == 0
    assert caget(ioc_ptc10.pvs["pid1_voltage_rbv"], use_monitor=False) == 0
    assert caget(ioc_ptc10.pvs["tc1_temperature"], use_monitor=False) == 21.3


@pytest.mark.skip(reason="Simulated IOCs are deprecated.")
def test_area_detector_ioc(ioc_area_detector):
    assert caget(ioc_area_detector.pvs["cam_acquire_busy"], use_monitor=False) == 0


@pytest.mark.skip(reason="Simulated IOCs are deprecated.")
def test_dxp_ioc_mca_propogation(ioc_dxp):
    # See if settings propogate to the MCAs
    caput("255idDXP:PresetLive", 1.5)
    caput("255idDXP:PresetReal", 2.5)
    # Check that the values were propogated
    preset_time = caget("255idDXP:mca1.PLTM", use_monitor=False)
    assert preset_time == 1.5
    real_time = caget("255idDXP:mca1.PRTM", use_monitor=False)
    assert real_time == 2.5


@pytest.mark.skip(reason="Simulated IOCs are deprecated.")
def test_dxp_ioc_spectra(ioc_dxp):
    # Get the starting spectrum
    spectrum = caget("255idDXP:mca1.VAL")
    assert not any(spectrum)
    # Start acquring spectra
    caput("255idDXP:PresetReal", 1.0)
    caput("255idDXP:StartAll", 1)
    assert caget("255idDXP:Acquiring", use_monitor=False) == 1
    time.sleep(1.1)
    # Check that acquiring is finished and the spectrum was updated
    assert caget("255idDXP:Acquiring", use_monitor=False) == 0
    spectrum = caget("255idDXP:mca1.VAL")
    assert any(spectrum)
