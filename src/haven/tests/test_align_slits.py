"""An assortment of tests for plans defined in Haven.

More critical plans (e.g. xafs_scan) are tested in other test files.

"""

import warnings

import pytest
from ophyd import sim

from haven.plans._align_slits import align_slits


def test_align_slits(RE):
    """Check the plan to aligns the slits."""
    # Prepare a fake detector and slit motor
    slit_motor = sim.motor
    I0 = sim.SynGauss(
        "det",
        sim.motor,
        "motor",
        center=-0.5,
        Imax=1,
        sigma=1,
        labels={"detectors"},
    )
    # Execute the plan
    RE(align_slits(slit_motors=[slit_motor], ion_chamber=I0))
    # Check that the slit positions have been set
    assert slit_motor.position == pytest.approx(-0.5)


def test_warn_poor_fit(RE):
    """Check that the plan emits a warning when no good fit is detected."""
    # Prepare a fake detector and slit motor
    slit_motor = sim.motor
    I0 = sim.SynGauss(
        "det",
        sim.motor,
        "motor",
        center=-0.5,
        noise="poisson",
        noise_multiplier=100,
        Imax=1,
        sigma=1,
        labels={"detectors"},
    )
    # Execute the plan, catching warnings
    with warnings.catch_warnings(record=True) as w:
        # Cause all warnings to always be triggered.
        warnings.simplefilter("always")
        RE(align_slits(slit_motors=[slit_motor], ion_chamber=I0))
        # Check that a warning was raised
        assert len(w) >= 1
        messages = [str(w_.message) for w_ in w]
        target_message = "Poor fit while centering motor"
        assert any([target_message in msg for msg in messages])


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
