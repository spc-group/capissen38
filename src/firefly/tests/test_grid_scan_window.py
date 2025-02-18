import asyncio
from unittest import mock

import pytest
from bluesky_queueserver_api import BPlan
from ophyd_async.testing import set_mock_value
from qtpy import QtCore

from firefly.plans.grid_scan import GridScanDisplay


@pytest.fixture()
async def display(qtbot, sim_registry, sync_motors, async_motors, dxp, ion_chamber):
    display = GridScanDisplay()
    qtbot.addWidget(display)
    await display.update_devices(sim_registry)
    display.ui.run_button.setEnabled(True)
    try:
        yield display
    finally:
        await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_time_calculator(display, sim_registry, ion_chamber):
    # set up motor num
    await display.update_regions(2)

    # set up num of repeat scans
    display.ui.spinBox_repeat_scan_num.setValue(6)

    # set up scan num of points
    display.regions[0].scan_pts_spin_box.setValue(4)
    display.regions[1].scan_pts_spin_box.setValue(5)

    # set up detectors
    display.ui.detectors_list.selected_detectors = mock.MagicMock(
        return_value=["vortex_me4", ion_chamber.name]
    )

    # set up default timing for the detector
    detectors = display.ui.detectors_list.selected_detectors()
    detectors = {name: sim_registry[name] for name in detectors}
    set_mock_value(detectors[ion_chamber.name].default_time_signal, 0.82)
    detectors["vortex_me4"].default_time_signal.set(0.5).wait()

    # Run the time calculator
    await display.update_total_time()

    # Check whether time is calculated correctly for a single scan
    assert display.ui.label_hour_scan.text() == "0"
    assert display.ui.label_min_scan.text() == "0"
    assert display.ui.label_sec_scan.text() == "16.4"

    # Check whether time is calculated correctly including the repeated scan
    assert display.ui.label_hour_total.text() == "0"
    assert display.ui.label_min_total.text() == "1"
    assert display.ui.label_sec_total.text() == "38.4"


@pytest.mark.asyncio
async def test_step_size_calculation(display, qtbot):
    # Set up the display with 2 regions
    await display.update_regions(2)

    # Region 0: Set Start, Stop, and Points
    region_0 = display.regions[0]
    region_0.start_line_edit.setText("0")
    region_0.stop_line_edit.setText("10")
    region_0.scan_pts_spin_box.setValue(12)

    assert (
        region_0.step_size_line_edit.text() == "0.90909"
    ), "Step size should be 0.90909 for 11 points from 0 to 10."

    region_1 = display.regions[1]
    region_1.start_line_edit.setText("5")
    region_1.stop_line_edit.setText("15")
    region_1.scan_pts_spin_box.setValue(3)

    assert (
        region_1.step_size_line_edit.text() == "5"
    ), "Step size should be 5 for 3 points from 5 to 15."

    # Test invalid input for Region 0
    region_0.start_line_edit.setText("invalid")
    assert (
        region_0.step_size_line_edit.text() == "N/A"
    ), "Step size should be 'N/A' for invalid start input in Region 0."

    region_1.scan_pts_spin_box.setValue(1)
    assert (
        region_1.step_size_line_edit.text() == "N/A"
    ), "Step size should be 'N/A' for num_points = 1 in Region 1."

    # Reset valid values for Region 0
    region_0.start_line_edit.setText("10")
    region_0.stop_line_edit.setText("30")
    region_0.scan_pts_spin_box.setValue(1)

    assert (
        region_0.step_size_line_edit.text() == "N/A"
    ), "Step size should be N/A for 4 points from 10 to 30."


@pytest.mark.asyncio
async def test_grid_scan_plan_queued(
    display, sim_registry, ion_chamber, monkeypatch, qtbot
):
    await display.update_regions(2)

    # set up a test motor 1
    display.regions[0].motor_box.combo_box.setCurrentText("sync_motor_2")
    display.regions[0].start_line_edit.setText("1")
    display.regions[0].stop_line_edit.setText("111")
    display.regions[0].scan_pts_spin_box.setValue(5)

    # select snake for the first motor
    display.regions[0].snake_checkbox.setChecked(True)

    # set up a test motor 2
    display.regions[1].motor_box.combo_box.setCurrentText("async_motor_1")
    display.regions[1].start_line_edit.setText("2")
    display.regions[1].stop_line_edit.setText("222")
    display.regions[1].scan_pts_spin_box.setValue(10)

    # set up detector list
    display.ui.detectors_list.selected_detectors = mock.MagicMock(
        return_value=["vortex_me4", ion_chamber.name]
    )
    # set up meta data
    display.ui.lineEdit_sample.setText("sam")
    display.ui.comboBox_purpose.setCurrentText("test")
    display.ui.textEdit_notes.setText("notes")

    expected_item = BPlan(
        "rel_grid_scan",
        ["vortex_me4", "I00"],
        "async_motor_1",
        2.0,
        222.0,
        10,
        "sync_motor_2",
        1.0,
        111.0,
        5,
        snake_axes=["sync_motor_2"],
        md={"sample_name": "sam", "purpose": "test", "notes": "notes"},
    )

    def check_item(item):
        print(item.to_dict())
        print(expected_item.to_dict())
        return item.to_dict() == expected_item.to_dict()

    # Click the run button and see if the plan is queued
    with qtbot.waitSignal(
        display.queue_item_submitted, timeout=1000, check_params_cb=check_item
    ):
        qtbot.mouseClick(display.ui.run_button, QtCore.Qt.LeftButton)
