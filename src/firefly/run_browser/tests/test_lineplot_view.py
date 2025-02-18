import numpy as np
import pandas as pd
import pytest
from pyqtgraph import PlotWidget

from firefly.run_browser.lineplot_view import LineplotView


@pytest.fixture()
def view(qtbot):
    mp_view = LineplotView()
    qtbot.addWidget(mp_view)
    # Configure widgets
    mp_view.ui.x_signal_combobox.addItem("energy_energy")
    mp_view.ui.x_signal_combobox.setCurrentText("energy_energy")
    mp_view.ui.y_signal_combobox.addItem("I0-net_current")
    mp_view.ui.y_signal_combobox.addItem("It-net_current")
    mp_view.ui.y_signal_combobox.setCurrentText("It-net_current")
    mp_view.ui.r_signal_combobox.addItem("I0-net_current")
    mp_view.ui.r_signal_combobox.addItem("It-net_current")
    mp_view.ui.r_signal_combobox.setCurrentText("I0-net_current")
    mp_view.ui.r_signal_checkbox.setCheckState(True)
    mp_view.ui.logarithm_checkbox.setCheckState(True)
    mp_view.ui.invert_checkbox.setCheckState(True)
    mp_view.ui.gradient_checkbox.setCheckState(True)
    return mp_view


# Set up fake data
dataframe = pd.DataFrame(
    {
        "energy_energy": np.linspace(8333, 8533, num=101),
        "I0-net_current": np.linspace(1, 100, num=101),
        "It-net_current": np.linspace(101, 200, num=101),
    }
)
dataframes = {"7d1daf1d-60c7-4aa7-a668-d1cd97e5335f": dataframe}


data_keys = {
    "energy_energy": {
        "dtype": "number",
        "dtype_numpy": "<f8",
        "object_name": "energy",
        "shape": [],
        "units": "eV",
    },
    "ge_8element": {
        "dtype": "array",
        "dtype_numpy": "<u4",
        "external": "STREAM:",
        "object_name": "ge_8element",
        "shape": [8, 4096],
        "source": "ca://XSP_Ge_8elem:HDF1:FullFileName_RBV",
    },
    "ge_8element-element0-deadtime_factor": {
        "source": "ca://XSP_Ge_8elem:HDF1:FullFileName_RBV",
        "shape": [],
        "dtype": "number",
        "dtype_numpy": "<f8",
        "external": "STREAM:",
        "object_name": "ge_8element",
    },
    "I0-net_current": {
        "dtype": "number",
        "dtype_numpy": "<f8",
        "object_name": "I0",
        "shape": [],
        "source": "ca://25idVME:3820:scaler1.S0",
        "units": "A",
    },
    "It-net_current": {
        "dtype": "number",
        "dtype_numpy": "<f8",
        "object_name": "It",
        "shape": [],
        "source": "ca://25idVME:3820:scaler1.S0",
        "units": "A",
    },
}


def test_load_ui(view):
    """Make sure widgets were loaded from the UI file."""
    assert isinstance(view.ui.plot_widget, PlotWidget)


def test_signal_options(view):
    """
    We need to know:
    - data_keys
    - independent hints (scan axes)
    - dependent hints (device hints)

    Then each view can handle sorting out which signals it needs.

    Use '64e85e20-106c-48e6-b643-77e9647b0242' for testing in the
    haven-dev catalog.

    """
    comboboxes = [
        view.ui.x_signal_combobox,
        view.ui.y_signal_combobox,
        view.ui.r_signal_combobox,
    ]
    view.ui.use_hints_checkbox.setChecked(False)
    view.update_signal_widgets(data_keys, [], [])
    # Make sure we don't include array datasets
    for combobox in comboboxes:
        assert (
            combobox.findText("ge_8element") == -1
        ), f"ge_8element signal should not be in {combobox.objectName()}."
        assert (
            combobox.findText("ge_8element-element0-deadtime_factor") == -1
        ), f"ge_8element-element0-deadtime_factor signal should not be in {combobox.objectName()}."
        assert (
            combobox.findText("I0-net_current") > -1
        ), f"I0-net_current signal should be in {combobox.objectName()}."
        assert (
            combobox.findText("energy_energy") > -1
        ), f"energy_energy signal should be in {combobox.objectName()}."


def test_hinted_signal_options(view):
    """
    We need to know:
    - data_keys
    - independent hints (scan axes)
    - dependent hints (device hints)

    Then each view can handle sorting out which signals it needs.

    Use '64e85e20-106c-48e6-b643-77e9647b0242' for testing in the
    haven-dev catalog.

    """
    comboboxes = [
        view.ui.x_signal_combobox,
        view.ui.y_signal_combobox,
        view.ui.r_signal_combobox,
    ]
    view.ui.use_hints_checkbox.setChecked(True)
    view.update_signal_widgets(data_keys, ["energy_energy"], ["I0-net_current"])
    # Make sure we don't include array datasets
    for combobox in comboboxes:
        assert (
            combobox.findText("ge_8element") == -1
        ), f"ge_8element signal should not be in {combobox.objectName()}."
    # Check hinted X signals
    assert (
        view.ui.x_signal_combobox.findText("I0-net_current") == -1
    ), f"I0-net_current signal should not be in x-signal combobox."
    assert (
        view.ui.x_signal_combobox.findText("energy_energy") > -1
    ), f"energy_energy signal should be in x-signal combobox."
    # Check hinted Y signals
    assert (
        view.ui.y_signal_combobox.findText("I0-net_current") > -1
    ), f"I0-net_current signal should not be in x-signal combobox."
    assert (
        view.ui.y_signal_combobox.findText("energy_energy") == -1
    ), f"energy_energy signal should be in x-signal combobox."


def test_symbol_options(view):
    combobox = view.ui.symbol_combobox
    assert combobox.count() == 19


def test_change_symbol(view):
    """For now just make sure it doesn't raise exceptions."""
    view.plot(dataframes)
    view.change_symbol()


def test_plotting_data(view):
    # Check prepared data
    xdata, ydata = view.prepare_plotting_data(dataframe)
    It = dataframe["It-net_current"]
    I0 = dataframe["I0-net_current"]
    energy = dataframe["energy_energy"]
    np.testing.assert_array_almost_equal(ydata, np.gradient(np.log(I0 / It), energy))


def test_update_plot(view):
    view.use_hints_checkbox.setChecked(True)
    view.independent_hints = ["energy_energy"]
    view.dependent_hints = ["I0-net_current"]
    view.data_keys = data_keys
    # Update the plots
    view.plot(dataframes)
    # Check the data were plotted
    plot_item = view.ui.plot_widget.getPlotItem()
    assert len(plot_item.dataItems) == 1


def test_update_plot_mean(view):
    view.independent_hints = ["energy_energy"]
    view.dependent_hints = ["I0-net_current"]
    view.data_keys = data_keys
    view.ui.aggregator_combobox.setCurrentText("StDev")
    # Update the plots
    view.plot(dataframes)
    # Check the data were plotted
    plot_item = view.ui.plot_widget.getPlotItem()
    assert len(plot_item.dataItems) == 1


def test_axis_labels(view):
    xlabel, ylabel = view.axis_labels()
    assert xlabel == "energy_energy"
    assert ylabel == "grad(ln(I0-net_current/It-net_current))"


def test_swap_signals(view, qtbot):
    assert view.ui.y_signal_combobox.currentText() == "It-net_current"
    assert view.ui.r_signal_combobox.currentText() == "I0-net_current"
    view.swap_signals()
    assert view.ui.y_signal_combobox.currentText() == "I0-net_current"
    assert view.ui.r_signal_combobox.currentText() == "It-net_current"
