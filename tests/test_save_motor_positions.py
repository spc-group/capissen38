import logging
import os
import time
import time_machine
import pytz
from zoneinfo import ZoneInfo
import datetime as dt
from datetime import datetime

import epics
import pytest
from ophyd.sim import motor1, SynAxis, make_fake_device
from ophyd import EpicsMotor, Signal, Component as Cpt
from haven import (
    save_motor_position,
    registry,
    get_motor_position,
    list_motor_positions,
    recall_motor_position,
    list_current_motor_positions,
    HavenMotor,
)

log = logging.getLogger(__name__)

# Use a timezone we're not likely to be in for testing tz-aware behavior
fake_time = dt.datetime(2022, 8, 19, 19, 10, 51, tzinfo=ZoneInfo("Asia/Taipei"))

IOC_timeout = 40  # Wait up to this many seconds for the IOC to be ready

motor_prefix = "255idVME:"


class FakeHavenMotor(SynAxis):
    user_offset = Cpt(Signal, value=0, kind="config")


@pytest.fixture
def sim_motor_registry(sim_registry):
    # Create the motors
    motor1 = FakeHavenMotor(name="SLT V Upper")
    sim_registry.register(motor1)
    motor2 = FakeHavenMotor(name="SLT V Lower")
    sim_registry.register(motor2)
    yield sim_registry


@time_machine.travel(fake_time, tick=True)
def test_save_motor_position_by_device(mongodb):
    # Check that no entry exists before saving it
    result = mongodb.motor_positions.find_one({"name": motor1.name})
    assert result is None
    # Create motor devices
    motorA = SynAxis(name="Motor A")
    motorB = SynAxis(name="Motor B")
    motorA.wait_for_connection()
    motorB.wait_for_connection()
    # Move to some other motor position so we can tell it saved the right one
    motorA.set(11.0).wait(timeout=10)
    motorB.set(23.0).wait(timeout=10)
    # Save the current motor position
    save_motor_position(
        motorA, motorB, name="Sample center", collection=mongodb.motor_positions
    )
    # Check that the motors got saved
    result = mongodb.motor_positions.find_one({"name": "Sample center"})
    assert result is not None
    assert len(result["motors"]) == 2
    result_A = [r for r in result["motors"] if r["name"] == motorA.name][0]
    result_B = [r for r in result["motors"] if r["name"] == motorB.name][0]
    assert result_A["name"] == motorA.name
    assert result_A["readback"] == 11.0
    assert result_B["readback"] == 23.0
    # Check that the timestamp was saved (accurate to within a second)
    assert result["savetime"] == pytest.approx(time.time(), abs=1)


@time_machine.travel(fake_time, tick=True)
def test_save_motor_position_by_name(mongodb, sim_registry):
    # Check that no entry exists before saving it
    result = mongodb.motor_positions.find_one({"name": motor1.name})
    assert result is None
    # Get our simulated motors into the device registry
    motorA = FakeHavenMotor(name="Motor A")
    motorB = FakeHavenMotor(name="Motor B")
    motorA.wait_for_connection(timeout=20)
    motorB.wait_for_connection(timeout=20)
    # Register the new motors with the Haven instrument registry
    sim_registry.register(motorA)
    sim_registry.register(motorB)
    # Move to some other motor position so we can tell it saved the right one
    motorA.set(11.0).wait()
    motorA.user_offset.set(1.5).wait()
    motorB.set(23.0).wait()
    time.sleep(0.1)
    # Save the current motor position
    save_motor_position(
        "Motor A", "Motor B", name="Sample center", collection=mongodb.motor_positions
    )
    # Check that the motors got saved
    result = mongodb.motor_positions.find_one({"name": "Sample center"})
    assert result is not None
    assert len(result["motors"]) == 2
    result_A = [r for r in result["motors"] if r["name"] == motorA.name][0]
    result_B = [r for r in result["motors"] if r["name"] == motorB.name][0]
    assert result_A["name"] == motorA.name
    assert result_A["readback"] == 11.0
    assert result_B["readback"] == 23.0
    assert result_A["offset"] == 1.5
    # Check that the metadata saved
    assert result["savetime"] == pytest.approx(time.time(), abs=1)


def test_get_motor_position_by_uid(mongodb):
    uid = str(mongodb.motor_positions.find_one({"name": "Good position A"})["_id"])
    result = get_motor_position(uid=uid, collection=mongodb.motor_positions)
    assert result.name == "Good position A"
    assert result.motors[0].name == "SLT V Upper"
    assert result.motors[0].readback == 510.5


def test_get_motor_position_by_name(mongodb):
    result = get_motor_position(
        name="Good position A", collection=mongodb.motor_positions
    )
    assert result.name == "Good position A"
    assert result.motors[0].name == "SLT V Upper"
    assert result.motors[0].readback == 510.5


def test_get_motor_position_exceptions(mongodb):
    # Fails when no query params are given
    with pytest.raises(TypeError):
        get_motor_position(collection=mongodb.motor_positions)


def test_recall_motor_position(mongodb, sim_motor_registry):
    # Re-set the previous value
    uid = str(mongodb.motor_positions.find_one({"name": "Good position A"})["_id"])
    plan = recall_motor_position(uid=uid, collection=mongodb.motor_positions)
    messages = list(plan)
    # Check the plan output
    msg0 = messages[0]
    assert msg0.obj.name == "SLT V Upper"
    assert msg0.args[0] == 510.5
    msg1 = messages[1]
    assert msg1.obj.name == "SLT V Lower"
    assert msg1.args[0] == -211.93


@time_machine.travel(fake_time, tick=True)
def test_list_motor_positions(mongodb, capsys):
    # Do the listing
    list_motor_positions(collection=mongodb.motor_positions)
    # Check stdout for printed motor positions
    captured = capsys.readouterr()
    assert len(captured.out) > 0
    uid = str(mongodb.motor_positions.find_one({"name": "Good position A"})["_id"])
    timestamp = "2022-08-19 19:10:51"
    expected = (
        f'\n\033[1mGood position A\033[0m (uid="{uid}", timestamp={timestamp})\n'
        "┣━SLT V Upper: 510.5, offset: 0.0\n"
        "┗━SLT V Lower: -211.93, offset: None\n"
    )
    assert captured.out == expected


def test_motor_position_e2e(mongodb, ioc_motor):
    """Check that a motor position can be saved, then recalled using
    simulated IOC.

    """
    # Create an epics motor for setting values manually
    pv = ioc_motor.pvs["m1"]
    motor1 = EpicsMotor(pv, name="SLT V Upper")
    motor1.wait_for_connection(timeout=20)
    assert motor1.connected
    registry.register(motor1)
    registry.find(name="SLT V Upper")
    epics.caput(pv, 504.6)
    assert epics.caget(pv, use_monitor=False) == 504.6
    time.sleep(0.1)
    assert motor1.get(use_monitor=False).user_readback == 504.6
    # Save motor position
    uid = save_motor_position(
        motor1,
        name="starting point",
        collection=mongodb.motor_positions,
    )
    # Change to a different value
    epics.caput(pv, 520)
    time.sleep(0.1)
    assert epics.caget(pv, use_monitor=False) == 520
    assert motor1.get(use_monitor=False).user_readback == 520
    # Recall the saved position and see if it complies
    plan = recall_motor_position(uid=uid, collection=mongodb.motor_positions)
    msg = next(plan)
    assert msg.obj.name == "SLT V Upper"
    assert msg.args[0] == 504.6


@time_machine.travel(fake_time, tick=True)
def test_list_current_motor_positions(mongodb, capsys):
    # Get our simulated motors into the device registry
    with capsys.disabled():
        motorA = FakeHavenMotor(name="Motor A")
        motorB = FakeHavenMotor(name="Motor B")
        motorA.wait_for_connection()
        motorB.wait_for_connection()
        # Move to some other motor position so we can tell it saved the right one
        motorA.set(11.0).wait()
        motorA.user_offset.set(1.5).wait()
        motorB.set(23.0).wait()
    # List the current motor position
    list_current_motor_positions(motorA, motorB, name="Current motor positions")
    # Check stdout for printed motor positions
    captured = capsys.readouterr()
    assert len(captured.out) > 0
    timestamp = fake_time.strftime("%Y-%m-%d %H:%M:%S")
    timestamp = "2022-08-19 19:10:51"
    expected = (
        f"\n\033[1mCurrent motor positions\033[0m (timestamp={timestamp})\n"
        "┣━Motor A: 11.0, offset: 1.5\n"
        "┗━Motor B: 23.0, offset: 0.0\n"
    )
    assert captured.out == expected
