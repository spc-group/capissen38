from collections import OrderedDict
from unittest.mock import MagicMock

import numpy as np
import pytest
from ophyd import sim
from ophyd_async.epics.motor import Motor

from haven.plans import fly_scan, grid_fly_scan
from haven.plans._fly import FlyerCollector
from haven.preprocessors import baseline_decorator


@pytest.fixture()
def flyer(sim_registry, mocker):
    m1 = Motor("255idcVME:m1", name="m1")
    return m1


def test_set_fly_params(flyer):
    """Does the plan set the parameters of the flyer motor."""
    # step size == 10
    plan = fly_scan([], flyer, -20, 30, num=6, dwell_time=1.5)
    messages = list(plan)
    prep_msg = messages[4]
    assert prep_msg.command == "prepare"
    prep_info = prep_msg.args[0]
    assert prep_info.start_position == -20
    assert prep_info.end_position == 30
    assert prep_info.time_for_move == 9.0


def test_fly_scan_metadata(flyer, ion_chamber):
    """Does the plan set the parameters of the flyer motor."""
    md = {"spam": "eggs"}
    print(baseline_decorator)
    plan = fly_scan([ion_chamber], flyer, -20, 30, num=6, dwell_time=1, md=md)
    messages = list(plan)
    open_msg = messages[1]
    assert open_msg.command == "open_run"
    real_md = open_msg.kwargs
    expected_md = {
        "plan_args": {
            "detectors": list([repr(ion_chamber)]),
            "num": 6,
            "dwell_time": 1,
            "*args": (repr(flyer), -20, 30),
        },
        "plan_name": "fly_scan",
        "motors": [flyer.name],
        "detectors": [ion_chamber.name],
        "spam": "eggs",
    }
    assert real_md == expected_md


def test_collector_describe():
    # Dummy devices with data taken from actual ophyd devices
    aerotech = MagicMock()
    aerotech.describe_collect.return_value = {
        "positions": OrderedDict(
            [
                (
                    "aerotech_horiz",
                    {
                        "source": "PV:25idc:m1.RBV",
                        "dtype": "number",
                        "shape": [],
                        "units": "micron",
                        "lower_ctrl_limit": -28135.352,
                        "upper_ctrl_limit": 31864.648,
                        "precision": 7,
                    },
                ),
                (
                    "aerotech_horiz_user_setpoint",
                    {
                        "source": "PV:25idc:m1.VAL",
                        "dtype": "number",
                        "shape": [],
                        "units": "micron",
                        "lower_ctrl_limit": -28135.352,
                        "upper_ctrl_limit": 31864.648,
                        "precision": 7,
                    },
                ),
            ]
        )
    }
    I0 = MagicMock()
    I0.describe_collect.return_value = {
        "I0": OrderedDict(
            [
                (
                    "I0_net_counts",
                    {
                        "source": "PV:25idcVME:3820:scaler1_netA.D",
                        "dtype": "number",
                        "shape": [],
                        "units": "",
                        "lower_ctrl_limit": 0.0,
                        "upper_ctrl_limit": 0.0,
                        "precision": 0,
                    },
                )
            ]
        )
    }
    motor = MagicMock()
    motor.describe.return_value = OrderedDict(
        [
            (
                "motor",
                {
                    "source": "SIM:motor",
                    "dtype": "integer",
                    "shape": [],
                    "precision": 3,
                },
            ),
            (
                "motor_setpoint",
                {
                    "source": "SIM:motor_setpoint",
                    "dtype": "integer",
                    "shape": [],
                    "precision": 3,
                },
            ),
        ]
    )
    flyers = [aerotech, I0]
    collector = FlyerCollector(
        positioners=[aerotech],
        detectors=[I0],
        stream_name="primary",
        extra_signals=[motor],
        name="collector",
    )
    desc = collector.describe_collect()
    assert "primary" in desc.keys()
    assert list(desc["primary"].keys()) == [
        "aerotech_horiz",
        "aerotech_horiz_user_setpoint",
        "I0_net_counts",
        "motor",
        "motor_setpoint",
    ]
    assert (
        desc["primary"]["aerotech_horiz"]
        == aerotech.describe_collect()["positions"]["aerotech_horiz"]
    )


def test_collector_collect():
    aerotech = MagicMock()
    aerotech.predict.side_effect = [
        # These are the target data, but we need more events to simulate a flying motor
        {
            "data": {
                "aerotech_horiz": -1000.0,
                "aerotech_horiz_user_setpoint": -1000.0,
            },
            "timestamps": {
                "aerotech_horiz": 1691957265.6073308,
                "aerotech_horiz_user_setpoint": 1691957265.6073308,
            },
            "time": 1691957265.6073308,
        },
        {
            "data": {"aerotech_horiz": -800.0, "aerotech_horiz_user_setpoint": -800.0},
            "timestamps": {
                "aerotech_horiz": 1691957266.1137164,
                "aerotech_horiz_user_setpoint": 1691957266.1137164,
            },
            "time": 1691957266.1137164,
        },
    ]
    aerotech.collect.return_value = [
        {
            "data": {
                "aerotech_horiz": -1100.0,
                "aerotech_horiz_user_setpoint": -1100.0,
            },
            "timestamps": {
                "aerotech_horiz": 1691957265.354138,
                "aerotech_horiz_user_setpoint": 1691957265.354138,
            },
            "time": 1691957265.354138,
        },
        {
            "data": {"aerotech_horiz": -900.0, "aerotech_horiz_user_setpoint": -900.0},
            "timestamps": {
                "aerotech_horiz": 1691957265.8605237,
                "aerotech_horiz_user_setpoint": 1691957265.8605237,
            },
            "time": 1691957265.8605237,
        },
        {
            "data": {"aerotech_horiz": -700.0, "aerotech_horiz_user_setpoint": -700.0},
            "timestamps": {
                "aerotech_horiz": 1691957266.366909,
                "aerotech_horiz_user_setpoint": 1691957266.366909,
            },
            "time": 1691957266.366909,
        },
    ]
    I0 = MagicMock()
    I0.collect.return_value = [
        {
            "data": {"I0_net_counts": [0]},
            "timestamps": {"I0_net_counts": [1691957269.1575842]},
            "time": 1691957269.1575842,
        },
        {
            "data": {"I0_net_counts": [0]},
            "timestamps": {"I0_net_counts": [1691957269.0734286]},
            "time": 1691957269.0734286,
        },
    ]
    flyers = [aerotech, I0]
    motor = MagicMock()
    motor.read.return_value = OrderedDict(
        [
            ("motor", {"value": 119.983, "timestamp": 1692072398.879956}),
            ("motor_setpoint", {"value": 120.0, "timestamp": 1692072398.8799553}),
        ]
    )

    collector = FlyerCollector(
        detectors=[I0],
        positioners=[aerotech],
        stream_name="primary",
        name="flyer_collector",
        extra_signals=[motor],
    )
    events = list(collector.collect())
    expected_events = [
        {
            "data": {
                "I0_net_counts": [0],
                "aerotech_horiz": -1000.0,
                "aerotech_horiz_user_setpoint": -1000.0,
                "motor": 119.983,
                "motor_setpoint": 120.0,
            },
            "timestamps": {
                "I0_net_counts": [1691957269.1575842],
                "aerotech_horiz": 1691957265.6073308,
                "aerotech_horiz_user_setpoint": 1691957265.6073308,
                "motor": 1692072398.879956,
                "motor_setpoint": 1692072398.8799553,
            },
            "time": 1691957269.1575842,
        },
        {
            "data": {
                "I0_net_counts": [0],
                "aerotech_horiz": -800.0,
                "aerotech_horiz_user_setpoint": -800.0,
                "motor": 119.983,
                "motor_setpoint": 120.0,
            },
            "timestamps": {
                "I0_net_counts": [1691957269.0734286],
                "aerotech_horiz": 1691957266.1137164,
                "aerotech_horiz_user_setpoint": 1691957266.1137164,
                "motor": 1692072398.879956,
                "motor_setpoint": 1692072398.8799553,
            },
            "time": 1691957269.0734286,
        },
    ]
    assert len(events) == 2
    assert events == expected_events


@pytest.mark.skip(reason="grid scans are currently broken")
def test_fly_grid_scan(aerotech_flyer):
    flyer = aerotech_flyer
    stepper = sim.motor
    # step size == 10
    plan = grid_fly_scan(
        [], stepper, -100, 100, 11, flyer, -20, 30, 6, snake_axes=[flyer]
    )
    messages = list(plan)
    assert messages[0].command == "stage"
    assert messages[1].command == "open_run"
    # Check that we move the stepper first
    assert messages[2].command == "checkpoint"
    assert messages[3].command == "set"
    assert messages[3].args == (-100,)
    assert messages[4].command == "wait"
    # Check that flyer motor positions snake back and forth
    stepper_positions = [
        msg.args[0]
        for msg in messages
        if (msg.command == "set" and msg.obj.name == "motor")
    ]
    flyer_start_positions = [
        msg.args[0]
        for msg in messages
        if (
            msg.command == "set"
            and msg.obj.name == f"{flyer.name}_flyer_start_position"
        )
    ]
    flyer_end_positions = [
        msg.args[0]
        for msg in messages
        if (msg.command == "set" and msg.obj.name == f"{flyer.name}_flyer_end_position")
    ]
    assert stepper_positions == list(np.linspace(-100, 100, num=11))
    assert flyer_start_positions == [-20, 30, -20, 30, -20, 30, -20, 30, -20, 30, -20]
    assert flyer_end_positions == [30, -20, 30, -20, 30, -20, 30, -20, 30, -20, 30]


@pytest.mark.skip(reason="grid scans are currently broken")
def test_fly_grid_scan_metadata(sim_registry, aerotech_flyer, sim_ion_chamber):
    """Does the plan set the parameters of the flyer motor."""
    flyer = aerotech_flyer
    stepper = sim.motor
    md = {"spam": "eggs"}
    plan = grid_fly_scan(
        [sim_ion_chamber],
        stepper,
        -100,
        100,
        11,
        flyer,
        -20,
        30,
        6,
        snake_axes=[flyer],
        md=md,
    )
    # Check the metadata contained in the "open_run" message
    messages = list(plan)
    open_msg = messages[2]
    assert open_msg.command == "open_run"
    real_md = open_msg.kwargs
    expected_md = {
        "detectors": ["I00"],
        "motors": ("motor", flyer.name),
        "num_points": 66,
        "num_intervals": 65,
        "plan_args": {
            "detectors": [repr(sim_ion_chamber)],
            "args": [repr(stepper), -100, 100, 11, repr(flyer), -20, 30, 6],
        },
        "plan_name": "grid_fly_scan",
        "hints": {
            "gridding": "rectilinear",
            "dimensions": [(["motor"], "primary"), ([flyer.name], "primary")],
        },
        "shape": (11, 6),
        "extents": ([-100, 100], [-20, 30]),
        "snaking": (False, True),
        "plan_pattern": "outer_product",
        "plan_pattern_args": {
            "args": [
                repr(stepper),
                -100,
                100,
                11,
            ]
        },
        "plan_pattern_module": "bluesky.plan_patterns",
        "spam": "eggs",
    }
    assert real_md == expected_md


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
