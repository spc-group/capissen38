from unittest import mock

from haven.instrument import slits


def test_slits_tweak():
    """Test the PVs for the tweak forward/reverse."""
    slits_obj = slits.BladeSlits("255idc:KB_slits", name="KB_slits")
    # Check the inherited setpoint/readback PVs
    assert slits_obj.v.center.setpoint.pvname == "255idc:KB_slitsVcenter"
    assert slits_obj.v.center.readback.pvname == "255idc:KB_slitsVt2.D"
    # Check the tweak PVs
    assert (
        slits_obj.v.center.tweak_value.pvname == "255idc:KB_slitsVcenter_tweakVal.VAL"
    )
    assert slits_obj.v.center.tweak_reverse.pvname == "255idc:KB_slitsVcenter_tweak.A"
    assert slits_obj.v.center.tweak_forward.pvname == "255idc:KB_slitsVcenter_tweak.B"


def test_load_slits(sim_registry, monkeypatch):
    monkeypatch.setattr(slits, "await_for_connection", mock.AsyncMock())
    slits.load_slits()
    # Check that the slits were loaded
    devices = sim_registry.findall(label="slits")
    assert len(devices) == 2
    KB_slits = sim_registry.find(name="KB_slits")
    assert KB_slits.prefix == "vme_crate_ioc:KB"
    whitebeam_slits = sim_registry.find(name="whitebeam_slits")
    assert whitebeam_slits.prefix == "255ida:slits:US:"
    # Check that the right slits subclasses were used
    assert isinstance(KB_slits, slits.BladeSlits)
    assert isinstance(whitebeam_slits, slits.ApertureSlits)


def test_aperture_PVs():
    aperture = slits.ApertureSlits("255ida:slits:US:", name="whitebeam_slits")
    assert not aperture.connected
    assert hasattr(aperture, "h")
    assert hasattr(aperture.h, "center")
    assert aperture.h.center.user_readback.pvname == "255ida:slits:US:hCenter.RBV"
    assert aperture.v.center.user_readback.pvname == "255ida:slits:US:vCenter.RBV"
    assert aperture.h.size.user_readback.pvname == "255ida:slits:US:hSize.RBV"
    assert aperture.v.size.user_readback.pvname == "255ida:slits:US:vSize.RBV"
    # Check the derived signals are simple pass-throughs to the user readback/setpoint
    assert aperture.h.size.readback._derived_from.pvname == "255ida:slits:US:hSize.RBV"
    assert aperture.h.size.setpoint._derived_from.pvname == "255ida:slits:US:hSize.VAL"
