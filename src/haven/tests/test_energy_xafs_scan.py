import numpy as np
import pytest
from ophyd import sim

from haven import KRange, energy_scan, xafs_scan


@pytest.fixture()
def mono_motor():
    return sim.SynAxis(name="mono_energy", labels={"motors", "energies"})


@pytest.fixture()
def id_gap_motor():
    return sim.SynAxis(name="id_gap_energy", labels={"motors", "energies"})


@pytest.fixture()
def exposure_motor():
    return sim.Signal(name="exposure")


@pytest.fixture()
def energies():
    return np.linspace(8300, 8500, 100)


@pytest.fixture()
def I0(sim_registry):
    # Register an ion chamber
    I0 = sim.SynGauss(
        "I0",
        sim.motor,
        "motor",
        center=-0.5,
        Imax=1,
        sigma=1,
        labels={"ion_chambers"},
    )
    return I0


def test_energy_scan_basics(
    beamline_manager, mono_motor, id_gap_motor, energies, RE, tmp_path
):
    beamline_manager.local_storage.full_path._readback = str(tmp_path)
    exposure_time = 1e-3
    # Set up fake detectors and motors
    I0_exposure = sim.SynAxis(
        name="I0_exposure",
        labels={
            "exposures",
        },
    )
    It_exposure = sim.SynAxis(
        name="It_exposure",
        labels={
            "exposures",
        },
    )
    I0 = sim.SynGauss(
        name="I0",
        motor=mono_motor,
        motor_field="mono_energy",
        center=np.median(energies),
        Imax=1,
        sigma=1,
        labels={"detectors"},
    )
    It = sim.SynSignal(
        func=lambda: 1.0,
        name="It",
        exposure_time=exposure_time,
    )
    # Execute the plan
    scan = energy_scan(
        energies,
        detectors=[I0, It],
        exposure=exposure_time,
        energy_signals=[mono_motor, id_gap_motor],
        time_signals=[I0_exposure, It_exposure],
        md={"edge": "Ni_K"},
    )
    result = RE(scan, sample_name="xafs_sample")
    # Check that the mono and ID gap ended up in the right position
    # time.sleep(1.0)
    assert mono_motor.readback.get() == np.max(energies)
    # assert mono_motor.get().readback == np.max(energies)
    assert id_gap_motor.get().readback == np.max(energies)
    assert I0_exposure.get().readback == exposure_time
    assert It_exposure.get().readback == exposure_time


def test_raises_on_empty_positioners(RE, energies):
    with pytest.raises(ValueError):
        RE(energy_scan(energies, energy_signals=[]))


def test_saves_dspacing(mono, energies, I0, It):
    """Does the mono's d-spacing get added to metadata."""
    # Prepare the messages from the plan
    mono.d_spacing._readback = 1.5418
    msgs = list(
        energy_scan(
            energies,
            detectors=[It],
            energy_signals=[mono],
            time_signals=[It.exposure_time],
        )
    )
    # Find the metadata written by the plan
    for msg in msgs:
        if msg.command == "open_run":
            md = msg.kwargs
            break
    else:
        raise RuntimeError("No open run message found")
    # Check for the dspacing of the mono in the metadata
    assert md["d_spacing"] == 1.5418


def test_single_range(mono_motor, exposure_motor, I0):
    E0 = 10000
    expected_energies = np.arange(9990, 10001, step=1)
    expected_exposures = np.asarray([1.0])
    scan = xafs_scan(
        -10,
        1,
        1,
        0,
        E0=E0,
        energy_signals=[mono_motor],
        time_signals=[exposure_motor],
    )
    # Check that the mono motor is moved to the correct positions
    scan_list = list(scan)
    real_energies = [
        i.args[0] for i in scan_list if i[0] == "set" and i.obj.name == "mono_energy"
    ]
    np.testing.assert_equal(real_energies, expected_energies)
    # Check that the exposure is set correctly
    real_exposures = [
        i.args[0] for i in scan_list if i[0] == "set" and i.obj.name == "exposure"
    ]
    np.testing.assert_equal(real_exposures, expected_exposures)


def test_multi_range(mono_motor, exposure_motor, I0):
    E0 = 10000
    expected_energies = np.concatenate(
        [
            np.arange(9990, 10001, step=2),
            np.arange(10001, 10011, step=1),
        ]
    )
    expected_exposures = np.asarray([0.5, 1.0])
    scan = xafs_scan(
        -10,
        2,
        0.5,
        0,
        1,
        1.0,
        10,
        E0=E0,
        energy_signals=[mono_motor],
        time_signals=[exposure_motor],
    )
    # Check that the mono motor is moved to the correct positions
    scan_list = list(scan)
    real_energies = [
        i.args[0] for i in scan_list if i[0] == "set" and i.obj.name == "mono_energy"
    ]
    np.testing.assert_equal(real_energies, expected_energies)
    # Check that the exposure is set correctly
    real_exposures = [
        i.args[0] for i in scan_list if i[0] == "set" and i.obj.name == "exposure"
    ]
    np.testing.assert_equal(real_exposures, expected_exposures)


def test_exafs_k_range(mono_motor, exposure_motor, I0):
    """Ensure that passing in k_min, etc. produces an energy range
    in K-space.

    """
    E0 = 10000
    E_min = 10
    k_min = 1.6200877248145786
    krange = KRange(k_min=k_min, k_max=14, k_step=0.5, k_weight=0.5, exposure=0.75)
    expected_energies = krange.energies() + E0
    expected_exposures = krange.exposures()
    scan = xafs_scan(
        E_min=10,
        k_step=0.5,
        k_max=14,
        k_exposure=0.75,
        k_weight=0.5,
        E0=E0,
        energy_signals=[mono_motor],
        time_signals=[exposure_motor],
    )
    # Check that the mono motor is moved to the correct positions
    scan_list = list(scan)
    real_energies = [
        i.args[0] for i in scan_list if i[0] == "set" and i.obj.name == "mono_energy"
    ]
    np.testing.assert_equal(real_energies, expected_energies)
    # Check that the exposure is set correctly
    real_exposures = [
        i.args[0] for i in scan_list if i[0] == "set" and i.obj.name == "exposure"
    ]
    np.testing.assert_equal(real_exposures, expected_exposures)


def test_named_E0(mono_motor, exposure_motor, I0):
    expected_energies = np.concatenate(
        [
            np.arange(8323, 8334, step=2),
            np.arange(8334, 8344, step=1),
        ]
    )
    expected_exposures = np.asarray([0.5, 1.0])
    scan = xafs_scan(
        -10,
        2,
        0.5,
        0,
        1,
        1.0,
        10,
        E0="Ni_K",
        energy_signals=[mono_motor],
        time_signals=[exposure_motor],
    )
    # Check that the mono motor is moved to the correct positions
    scan_list = list(scan)
    real_energies = [
        i.args[0] for i in scan_list if i[0] == "set" and i.obj.name == "mono_energy"
    ]
    np.testing.assert_equal(real_energies, expected_energies)
    # Check that the exposure is set correctly
    real_exposures = [
        i.args[0] for i in scan_list if i[0] == "set" and i.obj.name == "exposure"
    ]
    np.testing.assert_equal(real_exposures, expected_exposures)


def test_uses_default_time_signals(dxp, mono_motor):
    """Test that the default time positioners are used if no specific ones are given."""
    scan = xafs_scan(
        -10, 2, 0.5, 0, detectors=[dxp], time_signals=None, energy_signals=[mono_motor]
    )
    msgs = list(scan)
    set_msgs = [m for m in msgs if m.command == "set" and dxp.name in m.obj.name]
    assert len(set_msgs) == 1
    time_msg = set_msgs[0]
    assert time_msg.obj is dxp.preset_real_time
    assert time_msg.args[0] == 0.5


def test_remove_duplicate_energies(mono_motor, exposure_motor, I0):
    plan = xafs_scan(
        -4,
        2,
        1.0,
        6,
        34,
        1.0,
        40,
        E0=8333,
        energy_signals=[mono_motor],
        time_signals=[exposure_motor],
    )
    msgs = list(plan)
    set_msgs = [m for m in msgs if m.command == "set" and m.obj.name == "mono_energy"]
    read_msgs = [m for m in msgs if m.command == "read" and m.obj.name == "I0"]
    energies = [m.args[0] for m in set_msgs]
    # Make sure we only read each point once
    assert len(read_msgs) == len(energies)


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
