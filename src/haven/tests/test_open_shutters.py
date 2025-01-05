import pytest
from bluesky.plan_stubs import trigger_and_read
from bluesky.plans import count
from bluesky.protocols import Triggerable
from ophyd_async.core import Device

from haven import open_shutters_wrapper
from haven.preprocessors.open_shutters import open_fast_shutters_wrapper


@pytest.fixture()
def detector(sim_registry):
    class Detector(Triggerable, Device):
        """A stubbed detector that can be triggered."""

        def trigger(self):
            pass

    det = Detector(name="detector")
    return det


@pytest.fixture()
def fast_shutter(sim_registry):
    class FastShutter(Device):
        _ophyd_labels_ = {"shutters", "fast_shutters"}

    shutter = FastShutter(name="fast_shutter")
    sim_registry.register(shutter)
    return shutter


@pytest.fixture()
def bad_shutter(sim_registry):
    class BadShutter(Device):
        _ophyd_labels_ = {"shutters"}
        allow_close = False

    shutter = BadShutter(name="bad_shutter")
    sim_registry.register(shutter)
    return shutter


@pytest.fixture()
def slow_shutter(sim_registry):
    class SlowShutter(Device):
        _ophyd_labels_ = {"shutters"}

    shutter = SlowShutter(name="slow_shutter")
    sim_registry.register(shutter)
    return shutter


def test_slow_shutter_wrapper(
    sim_registry, detector, bad_shutter, slow_shutter, fast_shutter
):
    # Build the wrapped plan
    plan = trigger_and_read([detector])
    plan = open_shutters_wrapper(plan, registry=sim_registry)
    # Check that the current shutter position was read
    read_msg = next(plan)
    assert read_msg.command == "read"
    assert read_msg.obj in [slow_shutter, fast_shutter]
    read_msg = plan.send({read_msg.obj.name: {"value": 1}})
    assert read_msg.command == "read"
    assert read_msg.obj in [slow_shutter, fast_shutter]
    # Check that the shutter was opened
    set_msg = plan.send({read_msg.obj.name: {"value": 1}})
    assert set_msg.command == "set"
    assert set_msg.obj is slow_shutter
    assert set_msg.args[0] == 0
    wait_msg = next(plan)
    assert wait_msg.kwargs["group"] == set_msg.kwargs["group"]
    # Were the shutters closed again?
    msgs = list(plan)
    set_msg = msgs[-3]
    assert set_msg.command == "set"
    assert set_msg.obj in [slow_shutter, fast_shutter]
    assert set_msg.args[0] == 1
    set_msg = msgs[-2]
    assert set_msg.command == "set"
    assert set_msg.obj in [slow_shutter, fast_shutter]
    assert set_msg.args[0] == 1
    wait_msg = msgs[-1]
    assert wait_msg.kwargs["group"] == set_msg.kwargs["group"]


def test_fast_shutter_wrapper(sim_registry, detector, fast_shutter):
    # Build the wrapped plan
    plan = count([detector], num=2)
    plan = open_fast_shutters_wrapper(plan, shutters=[fast_shutter])
    msgs = list(plan)
    # Check that the shutter opens before triggering
    trig_idxs = [idx for idx, msg in enumerate(msgs) if msg.command == "trigger"]
    for trig_idx in trig_idxs:
        set_msg = msgs[trig_idx - 2]
        assert set_msg.command == "set"
        assert set_msg.obj == fast_shutter
        assert set_msg.args == (0,)
    # Check that the shutter closes after waiting
    for idx in trig_idxs:
        set_msg = msgs[idx + 2]
        assert set_msg.command == "set"
        assert set_msg.obj == fast_shutter
        assert set_msg.args == (1,)
