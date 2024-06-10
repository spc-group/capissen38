from unittest import mock

from apstools.devices.aps_undulator import ApsUndulator
from bluesky_queueserver_api import BPlan
from ophyd.sim import make_fake_device
from qtpy import QtCore

import haven
from firefly.energy import EnergyDisplay

FakeMonochromator = make_fake_device(haven.instrument.monochromator.Monochromator)
FakeEnergyPositioner = make_fake_device(
    haven.instrument.energy_positioner.EnergyPositioner
)
FakeUndulator = make_fake_device(ApsUndulator)


def test_mono_caqtdm_macros(qtbot, ffapp, sim_registry):
    # Create fake device
    FakeMonochromator("mono_ioc", name="monochromator")
    FakeEnergyPositioner(
        mono_pv="mono_ioc:Energy",
        id_offset_pv="mono_ioc:ID_offset",
        id_tracking_pv="mono_ioc:ID_tracking",
        id_prefix="id_ioc",
        name="energy",
    )
    undulator = FakeUndulator("id_ioc:", name="undulator", labels={"xray_sources"})
    undulator.energy.pvname = "id_ioc:Energy"
    # Load display
    display = EnergyDisplay()
    display.launch_caqtdm = mock.MagicMock()
    # Check that the various caqtdm calls set up the right macros
    display.launch_mono_caqtdm()
    assert display.launch_caqtdm.called
    assert display.launch_caqtdm.call_args[1]["macros"] == {
        "P": "mono_ioc:",
        "MONO": "UP",
        "BRAGG": "ACS:m3",
        "GAP": "ACS:m4",
        "ENERGY": "Energy",
        "OFFSET": "Offset",
        "IDENERGY": "id_ioc:Energy",
    }


def test_id_caqtdm_macros(qtbot, ffapp, sim_registry):
    # Create fake device
    mono = FakeMonochromator("mono_ioc", name="monochromator")
    FakeEnergyPositioner(
        mono_pv="mono_ioc:Energy",
        id_offset_pv="mono_ioc:ID_offset",
        id_tracking_pv="mono_ioc:ID_tracking",
        id_prefix="id_ioc",
        name="energy",
    )
    FakeUndulator("id_ioc:", name="undulator", labels={"xray_sources"})
    # Load display
    display = EnergyDisplay()
    display.launch_caqtdm = mock.MagicMock()
    # Check that the various caqtdm calls set up the right macros
    display.launch_id_caqtdm()
    assert display.launch_caqtdm.called
    assert display.launch_caqtdm.call_args[1]["macros"] == {
        "ID": "id_ioc",
        "M": 2,
        "D": 2,
    }


def test_move_energy(qtbot, ffapp, sim_registry):
    mono = FakeMonochromator("mono_ioc", name="monochromator")
    FakeEnergyPositioner(
        mono_pv="mono_ioc:Energy",
        id_offset_pv="mono_ioc:ID_offset",
        id_tracking_pv="mono_ioc:ID_tracking",
        id_prefix="id_ioc",
        name="energy",
    )

    # Load display
    disp = EnergyDisplay()
    # Click the set energy button
    btn = disp.ui.set_energy_button
    expected_item = BPlan("set_energy", energy=8402.0)

    def check_item(item):
        return item.to_dict() == expected_item.to_dict()

    qtbot.keyClicks(disp.target_energy_lineedit, "8402")
    with qtbot.waitSignal(
        ffapp.queue_item_added, timeout=1000, check_params_cb=check_item
    ):
        qtbot.mouseClick(btn, QtCore.Qt.LeftButton)


def test_predefined_energies(qtbot, ffapp, sim_registry):
    # Create fake device
    mono = FakeMonochromator("mono_ioc", name="monochromator")
    FakeEnergyPositioner(
        mono_pv="mono_ioc:Energy",
        id_offset_pv="mono_ioc:ID_offset",
        id_tracking_pv="mono_ioc:ID_tracking",
        id_prefix="id_ioc",
        name="energy",
    )

    # Set up the required Application state
    # Load display
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
        combo_box.activated.emit(9)  # <- this shouldn't be necessary
    line_edit = disp.ui.target_energy_lineedit
    assert line_edit.text() == "8333.000"


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
