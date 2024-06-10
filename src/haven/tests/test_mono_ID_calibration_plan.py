from unittest.mock import MagicMock

import pytest
from ophyd import sim

from haven import mono_ID_calibration


@pytest.fixture()
def mono_motor(sim_registry):
    motor = sim.SynAxis(name="energy_mono_energy", labels={"motors", "energies"})
    yield motor


@pytest.fixture()
def pitch2_motor(sim_registry):
    motor = sim.SynAxis(name="monochromator_pitch2", labels={"motors"})
    yield motor


@pytest.fixture()
def id_motor(sim_registry):
    motor = sim.SynAxis(name="energy_id_energy", labels={"motors", "energies"})
    yield motor


@pytest.fixture()
def ion_chamber(sim_registry, id_motor):
    I0 = sim.SynGauss(
        "I0",
        id_motor,
        "energy_id_energy",
        center=8.0,
        Imax=1,
        sigma=1,
        labels={"ion_chambers"},
    )
    yield I0


@pytest.mark.skip(reason="``haven.plans.align_motor`` is deprecated.")
def test_moves_energy(mono_motor, id_motor, ion_chamber, pitch2_motor, event_loop, RE):
    """Simple test to ensure that the plan moves the mono and undulators
    to the right starting energy."""
    # Execute the plan
    id_motor.set(8)
    fit_model = MagicMock()
    RE(
        mono_ID_calibration(
            energies=[8000], energy_motor=mono_motor, fit_model=fit_model
        )
    )
    assert mono_motor.readback.get() == 8000.0


def test_aligns_pitch(mono_motor, id_motor, ion_chamber, pitch2_motor):
    fit_model = MagicMock()
    plan = mono_ID_calibration(
        energies=[8000], energy_motor=mono_motor, fit_model=fit_model
    )
    with pytest.warns(UserWarning):
        # Raises a warning because there's no data to fit
        messages = list(plan)
    device_names = [getattr(m.obj, "name", None) for m in messages]
    assert "monochromator_pitch2" in device_names


def test_aligns_mono_energy(mono_motor, id_motor, ion_chamber, pitch2_motor):
    fit_model = MagicMock()
    plan = mono_ID_calibration(
        energies=[8000], energy_motor=mono_motor, fit_model=fit_model
    )
    with pytest.warns(UserWarning):
        # Raises a warning because there's no data to fit
        messages = list(plan)
    id_messages = [
        m for m in messages if getattr(m.obj, "name", "") == "energy_id_energy"
    ]
    # Check that messages were produced for each point in the mono scan
    npts = 40  # Taken from `align_motor` plan
    assert len(id_messages) >= npts


@pytest.mark.skip(reason="``haven.plans.align_motor`` is deprecated.")
def test_fitting_callback(
    mono_motor, id_motor, ion_chamber, pitch2_motor, event_loop, RE
):
    fit_model = MagicMock()
    plan = mono_ID_calibration(
        energies=[8000, 9000], energy_motor=mono_motor, fit_model=fit_model
    )
    # Execute the plan in the runengine
    result = RE(plan)
    # Check that the fitting results are available
    fit_model.fit.assert_called_once()
    # assert False


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
