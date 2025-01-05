from haven.devices.shutter import ShutterState
from haven.plans import record_dark_current


def test_shutters_get_reset(shutters, ion_chamber):
    shutter = shutters[0]
    msgs = list(record_dark_current(ion_chambers=[ion_chamber], shutters=[shutter]))
    # Check the shutters get closed
    set_shutter_msg = msgs[1]
    assert set_shutter_msg.command == "set"
    assert set_shutter_msg.obj is shutter
    assert set_shutter_msg.args[0] == ShutterState.CLOSED
    # Check the shutters get re-opened
    set_shutter_msg = msgs[-2]
    assert set_shutter_msg.command == "set"
    assert set_shutter_msg.obj is shutter
    assert set_shutter_msg.args[0] == ShutterState.OPEN


def test_messages(shutters, ion_chamber):
    shutter = shutters[0]
    msgs = list(record_dark_current(ion_chambers=[ion_chamber], shutters=[shutter]))
    from pprint import pprint

    pprint(msgs)
    # Check the shutters get closed
    trigger_msg = msgs[3]
    assert trigger_msg.obj is ion_chamber
    assert trigger_msg.kwargs["record_dark_current"] is True
