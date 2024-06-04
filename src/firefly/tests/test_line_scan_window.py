from unittest import mock

import pytest
from bluesky_queueserver_api import BPlan
from ophyd.sim import make_fake_device
from ophyd import DynamicDeviceComponent as DCpt
from ophyd import Kind

from qtpy import QtCore

from firefly.plans.line_scan import LineScanDisplay
from firefly.application import FireflyApplication

from haven.instrument import motor
from haven.instrument.ion_chamber import IonChamber
from haven.instrument.dxp import DxpDetector
from haven.instrument.dxp import add_mcas as add_dxp_mcas

@pytest.fixture
def fake_motors(sim_registry):
    motor_names = ["motorA_m1", "motorA_m2"]
    motors = []
    for name in motor_names:
        this_motor = make_fake_device(motor.HavenMotor)(name=name, labels={"motors"})
        motors.append(this_motor)
    return motors

# class DxpVortex(DxpDetector):
#     mcas = DCpt(
#         add_dxp_mcas(range_=[0, 1, 2, 3]),
#         kind=Kind.normal | Kind.hinted,
#         default_read_attrs=[f"mca{i}" for i in [0, 1, 2, 3]],
#         default_configuration_attrs=[f"mca{i}" for i in [0, 1, 2, 3]],
#     )

# @pytest.fixture()
# def dxp(sim_registry):
#     FakeDXP = make_fake_device(DxpVortex)
#     vortex = FakeDXP(name="vortex_me4", labels={"vortex_me4"})
#     yield vortex

# @pytest.fixture()
# def I0(sim_registry):
#     """A fake ion chamber named 'I0' on scaler channel 2."""
#     FakeIonChamber = make_fake_device(IonChamber)
#     ion_chamber = FakeIonChamber(
#         prefix="scaler_ioc",
#         preamp_prefix="preamp_ioc:SR04:",
#         name="I0",
#         labels={"I0"},
#         ch_num=2,
#     )
#     return ion_chamber

def test_line_scan_plan_queued(ffapp, qtbot, sim_registry, fake_motors, dxp, I0):
    app = FireflyApplication.instance()
    display = LineScanDisplay()
    display.ui.run_button.setEnabled(True)

    # set up motor num
    display.ui.num_motor_spin_box.setValue(2)
    
    # set up num of repeat scans
    display.ui.spinBox_repeat_scan_num.setValue(6)
    display.update_regions()

    # set up a test motor 1
    display.regions[0].motor_box.combo_box.setCurrentText("motorA_m1")
    display.regions[0].start_line_edit.setText("1")
    display.regions[0].stop_line_edit.setText("111")

    # set up a test motor 2
    display.regions[1].motor_box.combo_box.setCurrentText("motorA_m2")
    display.regions[1].start_line_edit.setText("2")
    display.regions[1].stop_line_edit.setText("222")

    # set up scan num of points
    display.ui.scan_pts_spin_box.setValue(2)

    # time is calculated when the selection is changed
    display.ui.detectors_list.selected_detectors = mock.MagicMock(
        return_value=["vortex_me4", "I0"]
    )
    
    # # set up default timing for the detector
    detectors = display.ui.detectors_list.selected_detectors()
    detectors = {name : app.registry[name] for name in detectors}
    detectors["I0"].default_time_signal.set(1).wait(2)
    detectors["vortex_me4"].default_time_signal.set(0.5).wait(2)

    # trigger update_total_time by changing scan num
    display.ui.scan_pts_spin_box.setValue(10)

    # set up meta data
    display.ui.lineEdit_sample.setText("sam")
    display.ui.lineEdit_purpose.setText("test")
    display.ui.textEdit_notes.setText("notes")

    expected_item = BPlan(
        "scan",
        ["vortex_me4", "I0"],
        "motorA_m1",
        1.0,
        111.0,
        "motorA_m2",
        2.0,
        222.0,
        num=10,
        md={'sample': 'sam', 
            'purpose': 'test', 
            'notes': 'notes'
            },
    )

    def check_item(item):
        # check whether time is calculated correctly
        try:
            # Check whether time is calculated correctly for a single scan
            assert int(display.ui.label_hour_scan.text()) == 0
            assert int(display.ui.label_min_scan.text()) == 0
            assert int(display.ui.label_sec_scan.text()) == 10

            # # Check whether time is calculated correctly including the repeated scan
            assert int(display.ui.label_hour_total.text()) == 0
            assert int(display.ui.label_min_total.text()) == 1
            assert int(display.ui.label_sec_total.text()) == 0

            # # Check if the remaining dictionary items are equal
            assert item.to_dict() == expected_item.to_dict()
            

        except AssertionError as e:
            print(e)
            return False

        return True

    # Click the run button and see if the plan is queued
    with qtbot.waitSignal(
        ffapp.queue_item_added, timeout=1000, check_params_cb=check_item
    ):
        qtbot.mouseClick(display.ui.run_button, QtCore.Qt.LeftButton)
