import pytest
from bluesky_queueserver_api import BPlan
from ophyd.sim import make_fake_device
from qtpy import QtCore

from firefly.application import FireflyApplication
from firefly.plans.move_motor_window import MoveMotorDisplay
from haven.instrument import motor


@pytest.fixture
def fake_motors(sim_registry):
    motor_names = ["motorA_m1", "motorA_m2"]
    motors = []
    for name in motor_names:
        this_motor = make_fake_device(motor.HavenMotor)(name=name, labels={"motors"})
        motors.append(this_motor)
    return motors


def test_move_motor_plan_queued(ffapp, qtbot, sim_registry, fake_motors):
    app = FireflyApplication.instance()
    display = MoveMotorDisplay()
    display.ui.run_button.setEnabled(True)

    # set up motor num
    display.ui.num_motor_spin_box.setValue(2)

    # uncheck relative
    display.ui.relative_scan_checkbox.setChecked(False)

    display.update_regions()

    # set up a test motor 1
    display.regions[0].motor_box.combo_box.setCurrentText("motorA_m1")
    display.regions[0].position_line_edit.setText("111")

    # set up a test motor 2
    display.regions[1].motor_box.combo_box.setCurrentText("motorA_m2")
    display.regions[1].position_line_edit.setText("222")

    # set up meta data
    display.ui.lineEdit_sample.setText("sam")
    display.ui.lineEdit_purpose.setText("test")

    expected_item = BPlan(
        "mv",
        "motorA_m1",
        111.0,
        "motorA_m2",
        222.0,
        md={
            "sample": "sam",
            "purpose": "test",
        },
    )

    # print(item.to_dict())

    def check_item(item):
        return item.to_dict() == expected_item.to_dict()

    # Click the run button and see if the plan is queued
    with qtbot.waitSignal(
        ffapp.queue_item_added, timeout=1000, check_params_cb=check_item
    ):
        qtbot.mouseClick(display.ui.run_button, QtCore.Qt.LeftButton)
