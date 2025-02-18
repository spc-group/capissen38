from pprint import pprint
from unittest import mock

import numpy as np
import pytest
from bluesky_queueserver_api import BPlan
from qtpy import QtCore

from firefly.plans.xafs_scan import XafsScanDisplay

# default values for EXAFS scan
pre_edge = [-200, -50, 5]
xanes_region = [-50, 50, 0.5]
exafs_region = [50, 800, 0.5]
default_values = [pre_edge, xanes_region, exafs_region]


@pytest.fixture()
def display(qtbot):
    display = XafsScanDisplay()
    qtbot.addWidget(display)
    return display


def test_region_number(display):
    """Does changing the region number affect the UI?"""
    # Check that the display has the right number of rows to start with
    assert display.ui.regions_spin_box.value() == 3
    assert hasattr(display, "regions")
    assert len(display.regions) == 3

    # Check that regions can be inserted
    display.ui.regions_spin_box.setValue(5)
    assert len(display.regions) == 5

    # Check that regions can be removed
    display.ui.regions_spin_box.setValue(1)
    assert len(display.regions) == 1


def test_E0_checkbox(display):
    """Does selecting the E0 checkbox adjust the UI properly?"""
    # check whether extracted edge value is correct
    display.edge_combo_box.setCurrentText("Pt L3 (11500.8 eV)")
    display.ui.use_edge_checkbox.setChecked(True)

    # check whether the math is done correctly when switching off E0
    display.ui.use_edge_checkbox.setChecked(False)
    # check whether edge value is extracted correctly
    np.testing.assert_equal(display.edge_value, 11500.8)
    # K-space checkboxes should be disabled when E0 is unchecked
    assert not display.regions[0].k_space_checkbox.isEnabled()

    # check whether energy values is added correctly
    for i in range(len(default_values)):
        np.testing.assert_almost_equal(
            float(display.regions[i].start_line_edit.text()),
            default_values[i][0] + display.edge_value,
            decimal=3,
        )
        np.testing.assert_almost_equal(
            float(display.regions[i].stop_line_edit.text()),
            default_values[i][1] + display.edge_value,
            decimal=3,
        )
        np.testing.assert_almost_equal(
            float(display.regions[i].step_line_edit.text()),
            default_values[i][2],
            decimal=3,
        )

    # check whether k range is calculated right
    display.ui.use_edge_checkbox.setChecked(True)
    # K-space checkbox should become re-enabled after E0 is checked
    assert display.regions[-1].k_space_checkbox.isEnabled()
    display.regions[-1].k_space_checkbox.setChecked(True)
    np.testing.assert_almost_equal(
        float(display.regions[i].start_line_edit.text()), 3.6226, decimal=4
    )
    np.testing.assert_almost_equal(
        float(display.regions[i].stop_line_edit.text()), 14.4905, decimal=4
    )
    np.testing.assert_almost_equal(
        float(display.regions[i].step_line_edit.text()), 3.64069 - 3.6226, decimal=4
    )


def test_xafs_scan_plan_queued_energies(display, qtbot):
    display.edge_combo_box.setCurrentText("Pt L3 (11500.8 eV)")
    display.regions[-1].region_checkbox.setChecked(False)
    # Set up detector list
    display.ui.detectors_list.selected_detectors = mock.MagicMock(
        return_value=["vortex_me4", "I0"]
    )
    energies_region0 = np.arange(
        default_values[0][0],
        default_values[0][1] + default_values[0][2],
        default_values[0][2],
    )
    energies_region1 = np.arange(
        default_values[1][0] + default_values[1][2],
        default_values[1][1] + default_values[1][2],
        default_values[1][2],
    )
    energies_merge = np.hstack([energies_region0, energies_region1])
    exposures = np.ones(energies_merge.shape)

    # set up meta data
    display.ui.lineEdit_sample.setText("sam")
    display.ui.checkBox_is_standard.setChecked(True)
    display.ui.comboBox_purpose.setCurrentText("test")
    display.ui.textEdit_notes.setText("sam_notes")

    expected_item = BPlan(
        "energy_scan",
        energies=energies_merge,
        exposure=exposures,
        E0=11500.8,
        detectors=["vortex_me4", "I0"],
        md={
            "sample_name": "sam",
            "purpose": "test",
            "is_standard": True,
            "notes": "sam_notes",
        },
    )

    def check_item(item):
        item_dict = item.to_dict()["kwargs"]
        expected_dict = expected_item.to_dict()["kwargs"]

        try:
            # Check energies & exposures within 3 decimals
            np.testing.assert_array_almost_equal(
                item_dict["energies"], expected_dict["energies"], decimal=3
            )
            np.testing.assert_array_almost_equal(
                item_dict["exposure"], expected_dict["exposure"], decimal=3
            )

            # Now check the rest of the dictionary, excluding the numpy array keys
            item_dict.pop("energies")
            item_dict.pop("exposure")
            expected_dict.pop("energies")
            expected_dict.pop("exposure")

            # Check if the remaining dictionary items are equal
            assert item_dict == expected_dict, "Non-array items do not match."

        except AssertionError as e:
            # Print detailed debug info
            pprint(item_dict)
            pprint(expected_dict)
            print(str(e))
            return False
        return True

    # Click the run button and see if the plan is queued
    display.ui.run_button.setEnabled(True)
    with qtbot.waitSignal(
        display.queue_item_submitted, timeout=1000, check_params_cb=check_item
    ):
        qtbot.mouseClick(display.ui.run_button, QtCore.Qt.LeftButton)


def test_xafs_scan_plan_queued_energies_k_mixed(qtbot, display):
    display.ui.regions_spin_box.setValue(2)
    display.edge_combo_box.setCurrentText("Pt L3 (11500.8 eV)")

    # set up the first region
    display.regions[0].start_line_edit.setText("-20")
    display.regions[0].stop_line_edit.setText("40")
    display.regions[0].step_line_edit.setText("10")

    # set up the second region
    display.regions[1].start_line_edit.setText("50")
    display.regions[1].stop_line_edit.setText("800")

    # convert to k space
    display.regions[1].k_space_checkbox.setChecked(True)
    display.regions[1].step_line_edit.setText("5")
    display.regions[1].weight_spinbox.setValue(2)

    # set up detector list
    display.ui.detectors_list.selected_detectors = mock.MagicMock(
        return_value=["vortex_me4", "I0"]
    )

    # set repeat scan num to 2
    display.ui.spinBox_repeat_scan_num.setValue(3)

    energies = np.array(
        [
            -20,
            -10,
            0,
            10,
            20,
            30,
            40,
            50,
            283.27,
            707.04,
        ]  # k values obtained from Athena software to double confirm ours
    )
    exposures = np.array(
        [1, 1, 1, 1, 1, 1, 1, 1, 5.665, 14.141]
    )  # k exposures kmin 3.62263

    # set up meta data
    display.ui.lineEdit_sample.setText("sam")
    display.ui.textEdit_notes.setText("sam_notes")

    expected_item = BPlan(
        "energy_scan",
        energies=energies,
        exposure=exposures,
        E0=11500.8,
        detectors=["vortex_me4", "I0"],
        md={
            "sample_name": "sam",
            "is_standard": False,
            "notes": "sam_notes",
        },
    )

    def check_item(item):
        item_dict = item.to_dict()["kwargs"]
        expected_dict = expected_item.to_dict()["kwargs"]

        try:
            # Check whether time is calculated correctly for a single scan
            assert display.ui.label_hour_scan.text() == "0"
            assert display.ui.label_min_scan.text() == "0"
            assert display.ui.label_sec_scan.text() == "27.8"

            # Check whether time is calculated correctly including the repeated scan
            assert display.ui.label_hour_total.text() == "0"
            assert display.ui.label_min_total.text() == "1"
            assert display.ui.label_sec_total.text() == "23.4"

            # Check energies & exposures within 3 decimals
            np.testing.assert_array_almost_equal(
                item_dict["energies"], expected_dict["energies"], decimal=2
            )
            np.testing.assert_array_almost_equal(
                item_dict["exposure"], expected_dict["exposure"], decimal=2
            )

            # Now check the rest of the dictionary, excluding the numpy array keys
            item_dict.pop("energies")
            item_dict.pop("exposure")
            expected_dict.pop("energies")
            expected_dict.pop("exposure")

            # Check if the remaining dictionary items are equal
            assert item_dict == expected_dict, "Non-array items do not match."

        except AssertionError as e:
            print(e)
            return False
        return True

    # Click the run button and see if the plan is queued
    display.ui.run_button.setEnabled(True)
    with qtbot.waitSignal(
        display.queue_item_submitted, timeout=1000, check_params_cb=check_item
    ):
        qtbot.mouseClick(display.ui.run_button, QtCore.Qt.LeftButton)


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
