from unittest import mock

import pytest
from ophyd.sim import make_fake_device

from firefly.kb_mirrors import KBMirrorsDisplay
from haven.instrument.mirrors import KBMirrors


@pytest.fixture()
def kb_mirrors(sim_registry):
    """A fake set of slits using the 4-blade setup."""
    FakeMirrors = make_fake_device(KBMirrors)
    kb = FakeMirrors(
        prefix="255idc:KB:",
        name="kb_mirrors",
        horiz_upstream_motor="255idc:m1",
        vert_upstream_motor="255idc:m2",
        horiz_downstream_motor="255idc:m3",
        vert_downstream_motor="255idc:m4",
        labels={"kb_mirrors"},
    )
    return kb


@pytest.fixture()
def kb_bendable_mirrors(sim_registry):
    """A fake set of slits using the 4-blade setup."""
    FakeMirrors = make_fake_device(KBMirrors)
    kb = FakeMirrors(
        prefix="255idc:Long_KB:",
        name="kb_bendable_mirrors",
        horiz_upstream_motor="255idc:m5",
        vert_upstream_motor="255idc:m6",
        horiz_downstream_motor="255idc:m7",
        vert_downstream_motor="255idc:m8",
        horiz_upstream_bender="255idc:m21",
        vert_upstream_bender="255idc:m22",
        horiz_downstream_bender="255idc:m23",
        vert_downstream_bender="255idc:m24",
        labels={"kb_mirrors"},
    )
    return kb


@pytest.fixture()
def display(ffapp, kb_mirrors):
    disp = KBMirrorsDisplay(macros={"DEVICE": kb_mirrors.name})
    return disp


def test_bender_widgets(ffapp, kb_bendable_mirrors):
    # Make the display object
    mirrors = kb_bendable_mirrors
    disp = KBMirrorsDisplay(macros={"DEVICE": mirrors.name})
    # Check that the bender control widgets were enabled
    assert disp.ui.horizontal_upstream_display.isEnabled()
    assert disp.ui.horizontal_downstream_display.isEnabled()
    assert disp.ui.vertical_upstream_display.isEnabled()
    assert disp.ui.vertical_downstream_display.isEnabled()


def test_kb_mirrors_caqtdm(display, kb_mirrors):
    display._open_caqtdm_subprocess = mock.MagicMock()
    # Launch the caqtdm display
    display.launch_caqtdm()
    assert display._open_caqtdm_subprocess.called
    cmds = display._open_caqtdm_subprocess.call_args[0][0]
    # Check that the right macros are sent
    # /net/s25data/xorApps/ui/KB_mirrors.ui, macro:
    # P=25idcVME:,PM=25idcVME:,KB=KB,KBH=KB:H,KBV=KB:V,KBHUS=m6,KBHDS=m5,KBVUS=m8,KBVDS=m7,KB1=KBH, KB2=KBV
    macros = [cmds[i + 1] for i in range(len(cmds)) if cmds[i] == "-macro"][0]
    assert "P=255idc:" in macros
    assert "KB=KB" in macros
    assert "KBH=KB:H" in macros
    assert "KBV=KB:V" in macros
    assert "KBHUS=m1" in macros
    assert "KBHDS=m3" in macros
    assert "KBVUS=m2" in macros
    assert "KBVDS=m4" in macros
    assert "KB1=KBH" in macros
    assert "KB2=KBV" in macros
    # Check that the right UI file is being used
    ui_file = cmds[-1]
    assert ui_file.split("/")[-1] == "KB_mirrors.ui"


def test_kb_bendable_mirrors_caqtdm(ffapp, kb_bendable_mirrors):
    mirrors = kb_bendable_mirrors
    disp = KBMirrorsDisplay(macros={"DEVICE": mirrors.name})
    disp._open_caqtdm_subprocess = mock.MagicMock()
    # Launch the caqtdm display
    disp.launch_caqtdm()
    assert disp._open_caqtdm_subprocess.called
    cmds = disp._open_caqtdm_subprocess.call_args[0][0]
    # Check that the right macros are sent
    # /net/s25data/xorApps/ui/KB_mirrors_and_benders.ui, macro: P=25idcVME:,PM=25idcVME:,KB=LongKB_Cdn,KBH=LongKB_Cdn:H,KBV=LongKB_Cdn:V,KBHUS=m50,KBHDS=m49,KBVUS=m56,KBVDS=m55,KB1=LongKB_CdnH, KB2=LongKB_CdnV,HBUS=m52,HBDS=m51,VBUS=m54,VBDS=m53
    macros = [cmds[i + 1] for i in range(len(cmds)) if cmds[i] == "-macro"][0]
    assert "P=255idc:" in macros
    assert "PM=255idc:" in macros
    assert "KB=Long_KB" in macros
    assert "KBH=Long_KB:H" in macros
    assert "KBV=Long_KB:V" in macros
    assert "KBHUS=m5" in macros
    assert "KBHDS=m7" in macros
    assert "KBVUS=m6" in macros
    assert "KBVDS=m8" in macros
    assert "KB1=Long_KBH" in macros
    assert "KB2=Long_KBV" in macros
    assert "HBUS=m21" in macros
    assert "HBDS=m23" in macros
    assert "VBUS=m22" in macros
    assert "VBDS=m24" in macros
    # Check that the right UI file is being used
    ui_file = cmds[-1]
    assert ui_file.split("/")[-1] == "KB_mirrors_and_benders.ui"
