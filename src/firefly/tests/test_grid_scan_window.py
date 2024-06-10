from unittest import mock

import pytest
from bluesky_queueserver_api import BPlan
from ophyd.sim import make_fake_device
from qtpy import QtCore

from firefly.application import FireflyApplication
from firefly.plans.grid_scan import GridScanDisplay
from haven.instrument import motor


@pytest.fixture
def fake_motors(sim_registry):
    motor_names = ["motorA_m1", "motorA_m2"]
    motors = []
    for name in motor_names:
        this_motor = make_fake_device(motor.HavenMotor)(name=name, labels={"motors"})
        sim_registry.register(this_motor)
        motors.append(this_motor)
    return motors


def test_time_calculator(qtbot, sim_registry, fake_motors, dxp, I0):
    app = FireflyApplication.instance()
    display = GridScanDisplay()
    qtbot.addWidget(display)

    # set up motor num
    display.ui.num_motor_spin_box.setValue(2)

    # set up num of repeat scans
    display.ui.spinBox_repeat_scan_num.setValue(6)

    # set up scan num of points
    display.ui.scan_pts_spin_box.setValue(10)

    # set up detectors
    display.ui.detectors_list.selected_detectors = mock.MagicMock(
        return_value=["vortex_me4", "I0"]
    )

    # set up default timing for the detector
    detectors = display.ui.detectors_list.selected_detectors()
    detectors = {name: app.registry[name] for name in detectors}
    detectors["I0"].default_time_signal.set(1).wait(2)
    detectors["vortex_me4"].default_time_signal.set(0.5).wait(2)

    # Create empty QItemSelection objects
    selected = QtCore.QItemSelection()
    deselected = QtCore.QItemSelection()

    # emit the signal so that the time calculator is triggered
    display.ui.detectors_list.selectionModel().selectionChanged.emit(
        selected, deselected
    )

    # Check whether time is calculated correctly for a single scan
    assert int(display.ui.label_hour_scan.text()) == 0
    assert int(display.ui.label_min_scan.text()) == 0
    assert int(display.ui.label_sec_scan.text()) == 20

    # Check whether time is calculated correctly including the repeated scan
    assert int(display.ui.label_hour_total.text()) == 0
    assert int(display.ui.label_min_total.text()) == 2
    assert int(display.ui.label_sec_total.text()) == 0


def test_grid_scan_plan_queued(ffapp, qtbot, sim_registry, fake_motors):
    display = GridScanDisplay()
    display.ui.run_button.setEnabled(True)
    display.ui.num_motor_spin_box.setValue(2)
    display.update_regions()

    # set up a test motor 1
    display.regions[0].motor_box.combo_box.setCurrentText("motorA_m1")
    display.regions[0].start_line_edit.setText("1")
    display.regions[0].stop_line_edit.setText("111")
    # select snake for the first motor
    display.regions[0].snake_checkbox.setChecked(True)

    # set up a test motor 2
    display.regions[1].motor_box.combo_box.setCurrentText("motorA_m2")
    display.regions[1].start_line_edit.setText("2")
    display.regions[1].stop_line_edit.setText("222")

    # set up scan num of points
    display.ui.scan_pts_spin_box.setValue(10)

    # set up detector list
    display.ui.detectors_list.selected_detectors = mock.MagicMock(
        return_value=["vortex_me4", "I0"]
    )

    # set up meta data
    display.ui.lineEdit_sample.setText("sam")
    display.ui.lineEdit_purpose.setText("test")
    display.ui.textEdit_notes.setText("notes")

    expected_item = BPlan(
        "grid_scan",
        ["vortex_me4", "I0"],
        "motorA_m1",
        1,
        111,
        "motorA_m2",
        2,
        222,
        num=10,
        snake_axes=["motorA_m1"],
        md={"sample": "sam", "purpose": "test", "notes": "notes"},
    )

    def check_item(item):
        return item.to_dict() == expected_item.to_dict()

    # Click the run button and see if the plan is queued
    with qtbot.waitSignal(
        ffapp.queue_item_added, timeout=1000, check_params_cb=check_item
    ):
        qtbot.mouseClick(display.ui.run_button, QtCore.Qt.LeftButton)
