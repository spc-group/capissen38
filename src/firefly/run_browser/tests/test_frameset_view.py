from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest
from qtpy.QtWidgets import QComboBox

from firefly.run_browser.frameset_view import FramesetView


@pytest.fixture()
def view(qtbot):
    fs_view = FramesetView()
    qtbot.addWidget(fs_view)
    return fs_view


def test_load_ui(view):
    """Make sure widgets were loaded from the UI file."""
    assert isinstance(view.ui.dataset_combobox, QComboBox)


def test_dataset_combobox_options(view):
    """
    We need to know:
    - external signals
    - internal signals
    - hints

    Then each view can handle sorting out which signals it needs.

    Use '64e85e20-106c-48e6-b643-77e9647b0242' for testing in the
    haven-dev catalog.

    """

    data_keys = {
        "ge_8element": {
            "dtype": "array",
            "dtype_numpy": "<u4",
            "external": "STREAM:",
            "object_name": "ge_8element",
            "shape": [8, 4096],
            "source": "ca://XSP_Ge_8elem:HDF1:FullFileName_RBV",
        },
        "I0-net_current": {
            "dtype": "number",
            "dtype_numpy": "<f8",
            "object_name": "I0",
            "shape": [],
            "source": "ca://25idVME:3820:scaler1.S0",
            "units": "A",
        },
        "I0-net_counts": {
            "dtype": "number",
            "dtype_numpy": "<u4",
            "object_name": "I0",
            "shape": [],
            "source": "ca://25idVME:3820:scaler1.S0",
            "units": "",
        },
    }
    ihints = ["sim_motor_2"]
    dhints = ["I0-net_current"]
    combobox = view.ui.dataset_combobox
    view.update_signal_widgets(data_keys, ihints, dhints)
    assert (
        combobox.findText("ge_8element") > -1
    ), f"ge_8element signal not in {combobox.objectName()}."
    assert (
        combobox.findText("I0-net_current") == -1
    ), f"I0-net_current signal should not be in {combobox.objectName()}."
    time_combobox = view.ui.time_signal_combobox
    assert (
        time_combobox.findText("ge_8element") == -1
    ), f"ge_8element signal should not be in {combobox.objectName()}."
    assert (
        time_combobox.findText("I0-net_current") > -1
    ), f"I0-net_current signal not in {combobox.objectName()}."
    assert (
        time_combobox.findText("I0-net_counts") > -1
    ), f"I0-net_counts signal not in {combobox.objectName()}."


def test_update_dimension_widgets(view):
    layout = view.ui.dimensions_layout
    view.update_dimension_widgets(shape=(21, 8, 4096))
    assert view.row_count(layout) == 4
    assert layout.itemAtPosition(1, 1).widget().text() == "21"
    assert layout.itemAtPosition(1, 2).widget().isChecked()
    assert layout.itemAtPosition(2, 1).widget().text() == "8"
    assert layout.itemAtPosition(2, 3).widget().isChecked()
    assert layout.itemAtPosition(3, 1).widget().text() == "4096"
    assert layout.itemAtPosition(3, 4).widget().isChecked()
    # New dimensions, does it update the rows?
    view.update_dimension_widgets(shape=(13, 21, 8, 4096))
    assert view.row_count(layout) == 5
    assert layout.itemAtPosition(1, 1).widget().text() == "13"
    assert layout.itemAtPosition(2, 1).widget().text() == "21"
    assert layout.itemAtPosition(3, 1).widget().text() == "8"
    assert layout.itemAtPosition(4, 1).widget().text() == "4096"


def test_radio_row_group(view):
    """Do other radio buttons get disabled when one is checked?"""
    layout = view.ui.dimensions_layout
    view.update_dimension_widgets(shape=(21, 8, 4096))
    z0_button = layout.itemAtPosition(1, 2).widget()
    y0_button = layout.itemAtPosition(1, 3).widget()
    x0_button = layout.itemAtPosition(1, 4).widget()
    z0_button.setChecked(True)
    assert not y0_button.isChecked()
    y0_button.setChecked(True)
    assert not z0_button.isChecked()


def test_radio_column_group(view):
    """Do other radio buttons get disabled when one is checked?"""
    layout = view.ui.dimensions_layout
    view.update_dimension_widgets(shape=(21, 8, 4096))
    z0_button = layout.itemAtPosition(1, 2).widget()
    z1_button = layout.itemAtPosition(2, 2).widget()
    z2_button = layout.itemAtPosition(3, 2).widget()
    z0_button.setChecked(True)
    assert not z1_button.isChecked()
    z1_button.setChecked(True)
    assert not z0_button.isChecked()


def test_disable_aggregate_comboboxes(view):
    """Do other combo boxes get disabled when a dimension is selected?"""
    layout = view.ui.dimensions_layout
    view.update_dimension_widgets(shape=(21, 8, 4096))
    z0_button = layout.itemAtPosition(1, 2).widget()
    combobox = layout.itemAtPosition(1, 5).widget()
    z0_button.setChecked(True)
    assert not combobox.isEnabled()


def test_reduce_dimensions_3d(view):
    data = np.mgrid[0:8, 0:51, 0:70, 0:102][0]
    # Make sure the dimension widgets are set up
    view.update_dimension_widgets(data)
    layout = view.ui.dimensions_layout
    z_pos, y_pos, x_pos = (2, 3, 4)
    layout.itemAtPosition(4, z_pos).widget().setChecked(True)
    layout.itemAtPosition(1, y_pos).widget().setChecked(True)
    layout.itemAtPosition(2, x_pos).widget().setChecked(True)
    # Apply dimensionality reduction
    new_data = view.reduce_dimensions(data)
    # Check results
    assert new_data.ndim == 3
    assert new_data.shape == (102, 8, 51)


def test_reduce_dimensions_2d(view):
    """1 of the dimensions gets reduced so we have a 2D image."""
    data = np.mgrid[0:8, 0:51, 0:70, 0:102][0]
    # Make sure the dimension widgets are set up
    view.update_dimension_widgets(data)
    layout = view.ui.dimensions_layout
    z_pos, y_pos, x_pos = (2, 3, 4)
    layout.itemAtPosition(4, z_pos).widget().setChecked(False)
    layout.itemAtPosition(4, 5).widget().setCurrentText("Mean")
    layout.itemAtPosition(1, y_pos).widget().setChecked(True)
    layout.itemAtPosition(2, x_pos).widget().setChecked(True)
    # Apply dimensionality reduction
    new_data = view.reduce_dimensions(data)
    # Check results
    assert new_data.ndim == 2
    assert new_data.shape == (8, 51)


def test_time_signal(view):
    """Check that the correct time signal gets provided to the plotting widgets."""
    # Set up
    df = pd.DataFrame(
        {
            "I0-net_current": np.linspace(0, 100, num=5),
        }
    )
    view.stash_data_frames({"": df})
    view.ui.time_signal_combobox.addItem("I0-net_current")
    view.ui.time_signal_combobox.setCurrentText("I0-net_current")
    plot_mock = MagicMock()
    view.ui.frame_view.setImage = plot_mock
    # Code under test
    view.plot_datasets({"": np.ones(shape=(5, 10, 15))})
    # Asserts
    assert plot_mock.called
    xvals = plot_mock.call_args[1]["xvals"]
    np.testing.assert_array_equal(xvals, df["I0-net_current"].values)
