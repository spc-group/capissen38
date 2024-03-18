from collections import OrderedDict
from unittest import mock

import numpy as np
import pytest
from ophyd import StatusBase

from haven import exceptions
from haven.instrument.aerotech import (
    AerotechFlyer,
    AerotechStage,
    load_aerotech_stages,
    ureg,
)


def test_load_aerotech_stage(sim_registry):
    load_aerotech_stages()
    # Make sure these are findable
    stage_ = sim_registry.find(name="aerotech")
    assert stage_ is not None
    vert_ = sim_registry.find(name="aerotech_vert")
    assert vert_ is not None


def test_aerotech_flyer(sim_registry):
    aeroflyer = AerotechFlyer(name="aerotech_flyer", axis="@0", encoder=6)
    assert aeroflyer is not None


def test_aerotech_stage(sim_registry):
    fly_stage = AerotechStage(
        "motor_ioc",
        pv_vert=":m1",
        pv_horiz=":m2",
        labels={"stages"},
        name="aerotech",
        delay_prefix="",
    )
    assert fly_stage is not None
    assert fly_stage.asyn.ascii_output.pvname == "motor_ioc:asynEns.AOUT"


def test_aerotech_fly_params_forward(aerotech_flyer):
    flyer = aerotech_flyer
    # Set some example positions
    flyer.motor_egu.set("micron").wait()
    flyer.acceleration.set(0.5).wait()  # sec
    flyer.encoder_resolution.set(0.001).wait()  # µm
    flyer.start_position.set(10.05).wait()  # µm
    flyer.end_position.set(19.95).wait()  # µm
    flyer.step_size.set(0.1).wait()  # µm
    flyer.dwell_time.set(1).wait()  # sec

    # Check that the fly-scan parameters were calculated correctly
    assert flyer.pso_start.get(use_monitor=False) == 10.0
    assert flyer.pso_end.get(use_monitor=False) == 20.0
    assert flyer.slew_speed.get(use_monitor=False) == 0.1  # µm/sec
    assert flyer.taxi_start.get(use_monitor=False) == 9.9  # µm
    assert flyer.taxi_end.get(use_monitor=False) == 20.0375  # µm
    assert flyer.encoder_step_size.get(use_monitor=False) == 100
    assert flyer.encoder_window_start.get(use_monitor=False) == -5
    assert flyer.encoder_window_end.get(use_monitor=False) == 10005
    i = 10.05
    pixel = []
    while i <= 19.98:
        pixel.append(i)
        i = i + 0.1
    np.testing.assert_allclose(flyer.pixel_positions, pixel)


def test_aerotech_fly_params_reverse(aerotech_flyer):
    flyer = aerotech_flyer
    # Set some example positions
    flyer.motor_egu.set("micron").wait()
    flyer.acceleration.set(0.5).wait()  # sec
    flyer.encoder_resolution.set(0.001).wait()  # µm
    flyer.start_position.set(19.95).wait()  # µm
    flyer.end_position.set(10.05).wait()  # µm
    flyer.step_size.set(0.1).wait()  # µm
    flyer.dwell_time.set(1).wait()  # sec

    # Check that the fly-scan parameters were calculated correctly
    assert flyer.pso_start.get(use_monitor=False) == 20.0
    assert flyer.pso_end.get(use_monitor=False) == 10.0
    assert flyer.slew_speed.get(use_monitor=False) == 0.1  # µm/sec
    assert flyer.taxi_start.get(use_monitor=False) == 20.1  # µm
    assert flyer.taxi_end.get(use_monitor=False) == 9.9625  # µm
    assert flyer.encoder_step_size.get(use_monitor=False) == 100
    assert flyer.encoder_window_start.get(use_monitor=False) == 5
    assert flyer.encoder_window_end.get(use_monitor=False) == -10005


def test_aerotech_fly_params_no_window(aerotech_flyer):
    """Test the fly scan params when the range is too large for the PSO window."""
    flyer = aerotech_flyer
    # Set some example positions
    flyer.motor_egu.set("micron").wait()
    flyer.acceleration.set(0.5).wait()  # sec
    flyer.encoder_resolution.set(0.001).wait()  # µm
    flyer.start_position.set(0).wait()  # µm
    flyer.end_position.set(9000).wait()  # µm
    flyer.step_size.set(0.1).wait()  # µm
    flyer.dwell_time.set(1).wait()  # sec

    # Check that the fly-scan parameters were calculated correctly
    assert flyer.pso_start.get(use_monitor=False) == -0.05
    assert flyer.pso_end.get(use_monitor=False) == 9000.05
    assert flyer.taxi_start.get(use_monitor=False) == pytest.approx(-0.15)  # µm
    assert flyer.taxi_end.get(use_monitor=False) == 9000.0875  # µm
    assert flyer.encoder_step_size.get(use_monitor=False) == 100
    assert flyer.encoder_window_start.get(use_monitor=False) == -5
    assert flyer.encoder_window_end.get(use_monitor=False) == 9000105
    assert flyer.encoder_use_window.get(use_monitor=False) is False


def test_aerotech_predicted_positions(aerotech_flyer):
    """Check that the fly-scan positions are calculated properly."""
    flyer = aerotech_flyer
    # Set some example positions
    flyer.motor_egu.set("micron").wait()
    flyer.acceleration.set(0.5).wait()  # sec
    flyer.encoder_resolution.set(0.001).wait()  # µm
    flyer.start_position.set(10.05).wait()  # µm
    flyer.end_position.set(19.95).wait()  # µm
    flyer.step_size.set(0.1).wait()  # µm
    flyer.dwell_time.set(1).wait()  # sec

    # Check that the fly-scan parameters were calculated correctly
    i = 10.05
    pixel_positions = []
    while i <= 19.98:
        pixel_positions.append(i)
        i = i + 0.1
    num_pulses = len(pixel_positions) + 1
    pso_positions = np.linspace(10, 20, num=num_pulses)
    encoder_pso_positions = np.linspace(0, 10000, num=num_pulses)
    np.testing.assert_allclose(flyer.encoder_pso_positions, encoder_pso_positions)
    np.testing.assert_allclose(flyer.pso_positions, pso_positions)
    np.testing.assert_allclose(flyer.pixel_positions, pixel_positions)


def test_enable_pso(aerotech_flyer):
    flyer = aerotech_flyer
    # Set up scan parameters
    flyer.encoder_step_size.set(50).wait()  # In encoder counts
    flyer.encoder_window_start.set(-5).wait()  # In encoder counts
    flyer.encoder_window_end.set(10000).wait()  # In encoder counts
    flyer.encoder_use_window.set(True).wait()
    # Check that commands are sent to set up the controller for flying
    flyer.enable_pso()
    assert flyer.send_command.called
    commands = [c.args[0] for c in flyer.send_command.call_args_list]
    assert commands == [
        "PSOCONTROL @0 RESET",
        "PSOOUTPUT @0 CONTROL 1",
        "PSOPULSE @0 TIME 20, 10",
        "PSOOUTPUT @0 PULSE WINDOW MASK",
        "PSOTRACK @0 INPUT 6",
        "PSODISTANCE @0 FIXED 50",
        "PSOWINDOW @0 1 INPUT 6",
        "PSOWINDOW @0 1 RANGE -5,10000",
    ]


def test_enable_pso_no_window(aerotech_flyer):
    flyer = aerotech_flyer
    # Set up scan parameters
    flyer.encoder_step_size.set(50).wait()  # In encoder counts
    flyer.encoder_window_start.set(-5).wait()  # In encoder counts
    flyer.encoder_window_end.set(None).wait()  # High end is outside the window range
    # Check that commands are sent to set up the controller for flying
    flyer.enable_pso()
    assert flyer.send_command.called
    commands = [c.args[0] for c in flyer.send_command.call_args_list]
    assert commands == [
        "PSOCONTROL @0 RESET",
        "PSOOUTPUT @0 CONTROL 1",
        "PSOPULSE @0 TIME 20, 10",
        "PSOOUTPUT @0 PULSE",
        "PSOTRACK @0 INPUT 6",
        "PSODISTANCE @0 FIXED 50",
        # "PSOWINDOW @0 1 INPUT 6",
        # "PSOWINDOW @0 1 RANGE -5,10000",
    ]


def test_pso_bad_window_forward(aerotech_flyer):
    """Check for an exception when the window is needed but not enabled.

    I.e. when the taxi distance is larger than the encoder step size."""
    flyer = aerotech_flyer
    # Set up scan parameters
    flyer.encoder_resolution.set(1).wait()
    flyer.encoder_step_size.set(
        5 / flyer.encoder_resolution.get()
    ).wait()  # In encoder counts
    flyer.encoder_window_start.set(-5).wait()  # In encoder counts
    flyer.encoder_window_end.set(None).wait()  # High end is outside the window range
    flyer.pso_end.set(100)
    flyer.taxi_end.set(110)
    # Check that commands are sent to set up the controller for flying
    with pytest.raises(exceptions.InvalidScanParameters):
        flyer.enable_pso()


def test_pso_bad_window_reverse(aerotech_flyer):
    """Check for an exception when the window is needed but not enabled.

    I.e. when the taxi distance is larger than the encoder step size."""
    flyer = aerotech_flyer
    # Set up scan parameters
    flyer.encoder_resolution.set(1).wait()
    flyer.step_size.set(5).wait()
    flyer.encoder_step_size.set(
        flyer.step_size.get() / flyer.encoder_resolution.get()
    ).wait()  # In encoder counts
    flyer.encoder_window_start.set(114).wait()  # In encoder counts
    flyer.encoder_window_start.set(None).wait()  # High end is outside the window range
    flyer.pso_start.set(100)
    flyer.taxi_start.set(94)
    # Check that commands are sent to set up the controller for flying
    with pytest.raises(exceptions.InvalidScanParameters):
        flyer.enable_pso()


def test_arm_pso(aerotech_flyer):
    flyer = aerotech_flyer
    assert not flyer.send_command.called
    flyer.arm_pso()
    assert flyer.send_command.called
    command = flyer.send_command.call_args.args[0]
    assert command == "PSOCONTROL @0 ARM"


def test_motor_units(aerotech_flyer):
    """Check that the motor and flyer handle enginering units properly."""
    flyer = aerotech_flyer
    flyer.motor_egu.set("micron").wait()
    unit = flyer.motor_egu_pint
    assert unit == ureg("1e-6 m")


def test_kickoff(aerotech_flyer):
    # Set up fake flyer with mocked fly method
    flyer = aerotech_flyer
    flyer.taxi = mock.MagicMock()
    flyer.dwell_time.set(1.0)
    # Start flying
    status = flyer.kickoff()
    # Check status behavior matches flyer interface
    assert isinstance(status, StatusBase)
    assert not status.done
    # Start flying and see if the status is done
    flyer.ready_to_fly.set(True).wait()
    status.wait()
    assert status.done
    assert type(flyer.starttime) == float


def test_complete(aerotech_flyer):
    # Set up fake flyer with mocked fly method
    flyer = aerotech_flyer
    flyer.move = mock.MagicMock()
    assert flyer.user_setpoint.get() == 0
    flyer.taxi_end.set(10).wait()
    # Complete flying
    status = flyer.complete()
    # Check that the motor was moved
    assert flyer.move.called_with(9)
    # Check status behavior matches flyer interface
    assert isinstance(status, StatusBase)
    status.wait()
    assert status.done


def test_predict(aerotech_flyer):
    flyer = aerotech_flyer
    # Create some fake fly scan data
    flyer._collected_data = {
        "user_readback": {
            "timestamps": [0, 1, 2, 3, 4, 5, 6],
            "values": [0., 100., 200., 300., 400., 500., 600.],
        }
    }
    # Set up needed parameters
    timestamp = 1.5
    prediction = flyer.predict(timestamp)
    assert prediction == {
        "time": 1.5,
        "timestamps": {
            "aerotech_horiz": 1.5,
        },
        "data": {
            "aerotech_horiz": 150.,
        }
    }


def test_describe_collect(aerotech_flyer):
    expected = {
        "aerotech_horiz": OrderedDict(
            [
                (
                    "aerotech_horiz",
                    {
                        "source": "SIM:aerotech_horiz",
                        "dtype": "integer",
                        "shape": [],
                        "precision": 3,
                    },
                ),
            ]
        )
    }

    assert aerotech_flyer.describe_collect() == expected


def test_fly_motor_positions(aerotech_flyer):
    flyer = aerotech_flyer
    # Arbitrary rest position
    flyer.user_setpoint.set(255).wait()
    flyer.parent.delay.channel_C.delay.sim_put(1.5)
    flyer.parent.delay.output_CD.polarity.sim_put(1)
    # Set example fly scan parameters
    flyer.taxi_start.set(5).wait()
    flyer.start_position.set(10).wait()
    flyer.pso_start.set(9.5).wait()
    flyer.taxi_end.set(105).wait()
    flyer.encoder_use_window.set(True).wait()
    # Mock the motor position so that it returns a status we control
    motor_status = StatusBase()
    motor_status.set_finished()
    mover = mock.MagicMock(return_value=motor_status)
    flyer.move = mover
    # Check the fly scan moved the motors in the right order
    flyer.taxi()
    flyer.fly()
    assert mover.called
    positions = [c.args[0] for c in mover.call_args_list]
    assert len(positions) == 3
    pso_arm, taxi, end = positions
    assert pso_arm == 9.5
    assert taxi == 5
    assert end == 105
    # Check that the delay generator is properly configured
    assert flyer.parent.delay.channel_C.delay.get(use_monitor=False) == 0.0
    assert flyer.parent.delay.output_CD.polarity.get(use_monitor=False) == 0


def test_aerotech_move_status(aerotech_flyer):
    """Check that the flyer only finishes when the readback value is reached."""
    flyer = aerotech_flyer
    status = flyer.move(100, wait=False)
    assert not status.done
    # To-Do: figure out how to make this be done in the fake device
    # assert status.done


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
