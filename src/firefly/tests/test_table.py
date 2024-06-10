from unittest import mock

import pytest
from ophyd.sim import make_fake_device

from firefly.table import TableDisplay
from haven.instrument import Table

FakeTable = make_fake_device(Table)


@pytest.fixture()
def table(sim_registry):
    """A fake set of slits using the 4-blade setup."""
    FakeTable = make_fake_device(Table)
    tbl = FakeTable(
        prefix="255idc:",
        name="table",
        upstream_motor="m1",
        downstream_motor="m2",
        horizontal_motor="m3",
        vertical_motor="m2",
        pseudo_motors="table_ds:",
        transforms="table_ds_trans:",
        labels={"tables"},
    )
    return tbl


@pytest.fixture()
def empty_table(sim_registry):
    """A fake set of slits using the 4-blade setup."""
    tbl = FakeTable(
        prefix="255idc:",
        name="table",
        labels={"tables"},
    )
    return tbl


@pytest.fixture()
def display(ffapp, table):
    disp = TableDisplay(macros={"DEVICE": table.name})
    return disp


def test_unused_motor_widgets(ffapp, empty_table):
    """Do control widgets get disable for motors that aren't on the device?"""
    display = TableDisplay(macros={"DEVICE": empty_table.name})
    # Check that the bender control widgets were enabled
    assert not display.ui.pitch_embedded_display.isEnabled()
    assert not display.ui.vertical_embedded_display.isEnabled()
    assert not display.ui.horizontal_embedded_display.isEnabled()


def test_tilting_table_caqtdm(ffapp, sim_registry):
    table = FakeTable(
        "255idcVME:",
        horizontal_motor="m4",
        upstream_motor="m42",
        downstream_motor="m43",
        transforms="table_ds_trans:",
        pseudo_motors="table_ds:",
        name="table",
    )
    display = TableDisplay(macros={"DEVICE": table.name})
    display._open_caqtdm_subprocess = mock.MagicMock()
    # Launch the caqtdm display
    display.launch_caqtdm()
    assert display._open_caqtdm_subprocess.called
    cmds = display._open_caqtdm_subprocess.call_args[0][0]
    # Check that the right macros are sent
    # /net/s25data/xorApps/ui/table_2leg.ui
    # macro: P=25idcVME:,PM=25idcVME:,TB=table_ds,TR=table_ds_trans,TBUS=m42,TBDS=m43,TBH=m4
    # Check that the right UI file is being used
    ui_file = cmds[-1]
    assert ui_file.split("/")[-1] == "table_2leg.ui"
    # Check the macros
    macros = [cmds[i + 1] for i in range(len(cmds)) if cmds[i] == "-macro"][0]
    assert "P=255idcVME:" in macros
    assert "PM=255idcVME:" in macros
    assert "TB=table_ds" in macros
    assert "TR=table_ds_trans" in macros
    assert "TBUS=m42" in macros
    assert "TBDS=m43" in macros
    assert "TBH=m4" in macros


def test_single_motor_caqtdm(ffapp, sim_registry):
    table = FakeTable("255idcVME:", horizontal_motor="m3", name="table")
    display = TableDisplay(macros={"DEVICE": table.name})
    display._open_caqtdm_subprocess = mock.MagicMock()
    # Launch the caqtdm display
    display.launch_caqtdm()
    assert display._open_caqtdm_subprocess.called
    cmds = display._open_caqtdm_subprocess.call_args[0][0]
    # Check that the right macros are sent
    # /APSshare/epics/synApps_6_2_1/support/motor-R7-2-2//motorApp/op/ui/autoconvert/motorx.ui
    # macro: P=25iddVME:,M=m45
    # Check that the right UI file is being used
    ui_file = cmds[-1]
    assert ui_file.split("/")[-1] == "motorx.ui"
    # Check the macros
    macros = [cmds[i + 1] for i in range(len(cmds)) if cmds[i] == "-macro"][0]
    assert "P=255idcVME:" in macros
    assert "M=m3" in macros


def test_double_motor_caqtdm(ffapp, sim_registry):
    table = FakeTable(
        "255idcVME:", horizontal_motor="m3", vertical_motor="m4", name="table"
    )
    display = TableDisplay(macros={"DEVICE": table.name})
    display._open_caqtdm_subprocess = mock.MagicMock()
    # Launch the caqtdm display
    display.launch_caqtdm()
    assert display._open_caqtdm_subprocess.called
    cmds = display._open_caqtdm_subprocess.call_args[0][0]
    # Check that the right macros are sent
    # /APSshare/epics/synApps_6_2_1/support/motor-R7-2-2//motorApp/op/ui/autoconvert/motor2x.ui,
    # macro: P=25idcVME:,M1=m9,M2=m10
    # Check that the right UI file is being used
    ui_file = cmds[-1]
    assert ui_file.split("/")[-1] == "motor2x.ui"
    # Check the macros
    macros = [cmds[i + 1] for i in range(len(cmds)) if cmds[i] == "-macro"][0]
    assert "P=255idcVME:" in macros
    assert "M1=m3" in macros
    assert "M2=m4" in macros


# def test_kb_bendable_mirrors_caqtdm(ffapp, kb_bendable_mirrors):
#     mirrors = kb_bendable_mirrors
#     disp = KBMirrorsDisplay(macros={"DEVICE": mirrors.name})
#     disp._open_caqtdm_subprocess = mock.MagicMock()
#     # Launch the caqtdm display
#     disp.launch_caqtdm()
#     assert disp._open_caqtdm_subprocess.called
#     cmds = disp._open_caqtdm_subprocess.call_args[0][0]
#     # Check that the right macros are sent
#     # /net/s25data/xorApps/ui/KB_mirrors_and_benders.ui, macro: P=25idcVME:,PM=25idcVME:,KB=LongKB_Cdn,KBH=LongKB_Cdn:H,KBV=LongKB_Cdn:V,KBHUS=m50,KBHDS=m49,KBVUS=m56,KBVDS=m55,KB1=LongKB_CdnH, KB2=LongKB_CdnV,HBUS=m52,HBDS=m51,VBUS=m54,VBDS=m53
#     macros = [cmds[i + 1] for i in range(len(cmds)) if cmds[i] == "-macro"][0]
#     assert "P=255idc:" in macros
#     assert "PM=255idc:" in macros
#     assert "KB=Long_KB" in macros
#     assert "KBH=Long_KB:H" in macros
#     assert "KBV=Long_KB:V" in macros
#     assert "KBHUS=m5" in macros
#     assert "KBHDS=m7" in macros
#     assert "KBVUS=m6" in macros
#     assert "KBVDS=m8" in macros
#     assert "KB1=Long_KBH" in macros
#     assert "KB2=Long_KBV" in macros
#     assert "HBUS=m21" in macros
#     assert "HBDS=m23" in macros
#     assert "VBUS=m22" in macros
#     assert "VBDS=m24" in macros
#     # Check that the right UI file is being used
#     ui_file = cmds[-1]
#     assert ui_file.split("/")[-1] == "KB_mirrors_and_benders.ui"
