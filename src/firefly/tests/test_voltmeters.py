import pytest
from bluesky_queueserver_api import BPlan

import haven
from firefly.main_window import FireflyMainWindow
from firefly.voltmeter import VoltmeterDisplay
from firefly.voltmeters import VoltmetersDisplay


@pytest.fixture()
def fake_ion_chambers(I0, It):
    return [I0, It]


def test_device(qtbot, ffapp, I0):
    ffapp.setup_window_actions()
    window = FireflyMainWindow()
    display = VoltmeterDisplay(macros={"IC": "I0"})
    assert hasattr(display, "_device")
    assert isinstance(display._device, haven.IonChamber)


def test_scaler_prefix(qtbot, ffapp, sim_registry):
    """Make sure the scaler prefix gets passed in as a macro."""
    # Set up fake ion chamber
    window = FireflyMainWindow()
    ic = haven.IonChamber(
        "",
        scaler_prefix="255idcVME:scaler1",
        ch_num=1,
        name="my_ion_chamber",
        labels={"ion_chambers"},
    )
    # Check the macros
    display = VoltmetersDisplay()
    assert display.macros()["SCALER"] == "255idcVME:scaler1"


def test_embedded_display_widgets(qtbot, fake_ion_chambers, ffapp):
    """Test the the voltmeters creates a new embedded display widget for
    each ion chamber.

    """
    window = FireflyMainWindow()
    # Load the display
    vms_display = VoltmetersDisplay()
    # Check that the embedded display widgets get added correctly
    assert hasattr(vms_display, "_ion_chamber_displays")
    assert len(vms_display._ion_chamber_displays) == 2
    # two displays and a separator
    assert vms_display.voltmeters_layout.count() == 3
    # Check that the embedded display widgets have the correct macros
    emb_disp = vms_display._ion_chamber_displays[0]
    disp = emb_disp.open_file(force=True)
    macros = disp.macros()
    assert macros == {"IC": "I0", "SCALER": "scaler_ioc"}
    # Check that a device has been created properly
    assert isinstance(disp._device, haven.IonChamber)


def test_ion_chamber_menu(fake_ion_chambers, qtbot, ffapp):
    ffapp.setup_window_actions()
    ffapp.setup_runengine_actions()
    # Create the window
    window = FireflyMainWindow()
    # Check that the menu items have been created
    assert hasattr(window.ui, "detectors_menu")
    assert hasattr(window.ui, "ion_chambers_menu")
    assert len(ffapp.ion_chamber_actions) == 2


def test_open_ion_chamber_window(fake_ion_chambers, ffapp):
    # Set up the application
    ffapp.setup_window_actions()
    ffapp.setup_runengine_actions()
    # Simulate clicking on the menu action (they're in alpha order)
    window = FireflyMainWindow()
    action = ffapp.ion_chamber_actions["It"]
    action.trigger()
    # See if the window was created
    ion_chamber_name = "FireflyMainWindow_ion_chamber_It"
    assert ion_chamber_name in ffapp.windows.keys()
    macros = ffapp.windows[ion_chamber_name].display_widget().macros()
    assert macros["IC"] == "It"
    # Clean up
    window.close()


def test_auto_gain_plan(fake_ion_chambers, ffapp, qtbot):
    # Set up the application
    ffapp.setup_window_actions()
    ffapp.setup_runengine_actions()
    window = FireflyMainWindow()
    display = VoltmetersDisplay()
    # Put input values into the widgets
    display.ui.volts_min_line_edit.setText("")
    display.ui.volts_max_line_edit.setText("")
    disp = display._ion_chamber_displays[0]
    # Check some boxes for which ion chambers get auto-gained
    for idx in [1]:
        ic_disp = display._ion_chamber_displays[idx]
        ic_disp._embedded_widget = ic_disp.open_file(force=True)
        ic_disp.embedded_widget.ui.auto_gain_checkbox.setChecked(True)
    # Check that the correct plan was sent
    expected_item = BPlan("auto_gain", ["It"])

    def check_item(item):
        return item.to_dict() == expected_item.to_dict()

    # Click the run button and see if the plan is queued
    with qtbot.waitSignal(
        ffapp.queue_item_added, timeout=1000, check_params_cb=check_item
    ):
        # Simulate clicking on the auto_gain button
        display.ui.auto_gain_button.click()


def test_auto_gain_plan_with_args(fake_ion_chambers, ffapp, qtbot):
    # Set up the application
    ffapp.setup_window_actions()
    ffapp.setup_runengine_actions()
    window = FireflyMainWindow()
    display = VoltmetersDisplay()
    # Put input values into the widgets
    display.ui.volts_min_line_edit.setText("1.0")
    display.ui.volts_max_line_edit.setText("4.5")
    # Check some boxes for which ion chambers get auto-gained
    for idx in [1]:
        ic_disp = display._ion_chamber_displays[idx]
        ic_disp._embedded_widget = ic_disp.open_file(force=True)
        ic_disp.embedded_widget.ui.auto_gain_checkbox.setChecked(True)
    # Check that the correct plan was sent
    expected_item = BPlan("auto_gain", ["It"], volts_min=1.0, volts_max=4.5)

    def check_item(item):
        return item.to_dict() == expected_item.to_dict()

    # Click the run button and see if the plan is queued
    with qtbot.waitSignal(
        ffapp.queue_item_added, timeout=1000, check_params_cb=check_item
    ):
        # Simulate clicking on the auto_gain button
        display.ui.auto_gain_button.click()


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
