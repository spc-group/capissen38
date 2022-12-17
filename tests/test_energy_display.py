import time
from unittest import mock

import pytest
from qtpy import QtWidgets, QtCore
from bluesky_queueserver_api import BPlan
import haven

from firefly.main_window import FireflyMainWindow
from firefly.energy import EnergyDisplay


def test_energy_macros(qtbot):
    # Create fake device
    mono = haven.instrument.monochromator.Monochromator("mono_ioc", name="monochromator")
    haven.registry.register(
        haven.instrument.energy_positioner.EnergyPositioner(mono_pv="",
                                                            id_prefix="ID25ds",
                                                            name="energy"))
    # Load display
    FireflyMainWindow()
    display = EnergyDisplay()
    # Check macros
    macros = display.macros()
    assert macros["MONO_MODE_PV"] == "mono_ioc:mode"
    assert macros["MONO_ENERGY_PV"] == "mono_ioc:Energy.RBV"
    assert macros["ID_ENERGY_PV"] == "ID25ds:Energy.VAL"
    assert macros["ID_GAP_PV"] == "ID25ds:Gap.VAL"


def test_move_energy(qtbot, qapp):
    # Load display
    FireflyMainWindow()
    disp = EnergyDisplay()
    # Click the set energy button
    btn = disp.ui.set_energy_button
    expected_item = BPlan('set_energy', energy=8402.0)
    def check_item(item):
        return item.to_dict() == expected_item.to_dict()
    qtbot.keyClicks(disp.target_energy_lineedit, '8402')
    with qtbot.waitSignal(qapp.queue_item_added, timeout=1000,
                          check_params_cb=check_item):
        qtbot.mouseClick(btn, QtCore.Qt.LeftButton)


def test_predefined_energies(qtbot, qapp):
    # Load display
    FireflyMainWindow()
    disp = EnergyDisplay()
    # Check that the combo box was populated
    combo_box = disp.ui.edge_combo_box
    assert combo_box.count() > 0
    assert combo_box.itemText(0) == "Select edge…"
    assert combo_box.itemText(1) == "Ca K (4038 eV)"
    # Does it filter energies outside the usable range?
    assert combo_box.count() < 250
    # Does it update the energy line edit?
    with qtbot.waitSignal(combo_box.activated, timeout=1000):
        qtbot.keyClicks(combo_box, "Ni K (8333 eV)\t")
    line_edit = disp.ui.target_energy_lineedit
    assert line_edit.text() == "8333.000"
