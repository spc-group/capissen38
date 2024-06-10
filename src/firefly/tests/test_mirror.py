from unittest import mock

import pytest
from ophyd.sim import make_fake_device

from firefly.mirror import MirrorDisplay
from haven.instrument.mirrors import BendableHighHeatLoadMirror, HighHeatLoadMirror


@pytest.fixture()
def hhl_mirror(sim_registry):
    """A fake set of slits using the 4-blade setup."""
    FakeMirrors = make_fake_device(HighHeatLoadMirror)
    mirr = FakeMirrors(prefix="255ida:ORM1:", name="hhl_mirror", labels={"mirrors"})
    return mirr


@pytest.fixture()
def hhl_bendable_mirror(sim_registry):
    """A fake set of slits using the 4-blade setup."""
    FakeMirrors = make_fake_device(BendableHighHeatLoadMirror)
    mirr = FakeMirrors(prefix="255ida:ORM1:", name="hhl_mirror", labels={"mirrors"})
    return mirr


@pytest.fixture()
def display(ffapp, hhl_mirror):
    disp = MirrorDisplay(macros={"DEVICE": hhl_mirror.name})
    return disp


def test_mirror_caqtdm(display, hhl_mirror):
    display._open_caqtdm_subprocess = mock.MagicMock()
    # Launch the caqtdm display
    display.launch_caqtdm()
    assert display._open_caqtdm_subprocess.called
    cmds = display._open_caqtdm_subprocess.call_args[0][0]
    # Check that the right macros are sent
    # /net/s25data/xorApps/epics/synApps_6_2/ioc/25ida/25idaApp/op/ui/HHLM_4.ui
    # macro: P=25ida:,MIR=ORM1:,Y=m1,ROLL=m2,LAT=lateral,CP=coarsePitch,,UPL=m3,DNL=m4
    macros = [cmds[i + 1] for i in range(len(cmds)) if cmds[i] == "-macro"][0]
    assert "P=255ida:" in macros
    assert "MIR=ORM1" in macros
    assert "Y=m1" in macros
    assert "ROLL=m2" in macros
    assert "LAT=lateral" in macros
    assert "CP=coarsePitch" in macros
    assert "UPL=m3" in macros
    assert "DNL=m4" in macros
    # Check that the right UI file is being used
    ui_file = cmds[-1]
    assert ui_file.split("/")[-1] == "HHLM_4.ui"


def test_bendable_mirror_caqtdm(hhl_bendable_mirror):
    mirror = hhl_bendable_mirror
    display = MirrorDisplay(macros={"DEVICE": mirror.name})
    display._open_caqtdm_subprocess = mock.MagicMock()
    # Launch the caqtdm display
    display.launch_caqtdm()
    assert display._open_caqtdm_subprocess.called
    cmds = display._open_caqtdm_subprocess.call_args[0][0]
    # Check that the right macros are sent
    # /net/s25data/xorApps/epics/synApps_6_2/ioc/25ida/25idaApp/op/ui/HHLM_4.ui
    # macro: P=25ida:,MIR=ORM1:,Y=m1,ROLL=m2,LAT=lateral,CP=coarsePitch,,UPL=m3,DNL=m4
    macros = [cmds[i + 1] for i in range(len(cmds)) if cmds[i] == "-macro"][0]
    assert "BEND=m5" in macros
    # Check that the right UI file is being used
    ui_file = cmds[-1]
    assert ui_file.split("/")[-1] == "HHLM_6.ui"


def test_bendable_mirror(hhl_bendable_mirror):
    mirror = hhl_bendable_mirror
    display = MirrorDisplay(macros={"DEVICE": mirror.name})
    # Check that the bender controls are unlocked
    assert display.ui.bender_embedded_display.isEnabled()

    # For a bendable HHL mirror
    # /net/s25data/xorApps/epics/synApps_6_2/ioc/25ida/25idaApp/op/ui/HHLM_6.ui, macro: P=25ida:,MIR=ORM2:,Y=m1,ROLL=m2,LAT=lateral,CP=coarsePitch,FP=PZT:m1,BEND=m5,UPL=m3,DNL=m4
