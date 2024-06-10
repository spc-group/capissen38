import logging

import numpy as np
import pytest

from haven import ERange, KRange, merge_ranges

# import unittest


logging.basicConfig(level=logging.INFO)

energy_range_parameters = [
    # (start, end,  step, expected_energies)
    (8300, 8400, 0.5, np.linspace(8300, 8400, num=201)),  # Example values
    (1, 1.3, 0.1, [1, 1.1, 1.2, 1.3]),  # Known float rounding error
    (0, 70, 50, [0, 50]),  # End-point is not a step multiple
    (1.3, 1.0, -0.1, [1.3, 1.2, 1.1, 1.0]),  # Reverse direction
]


@pytest.mark.parametrize("start,stop,step,expected_energies", energy_range_parameters)
def test_e_range(start, stop, step, expected_energies):
    """Test the ERange class for calculating energy points."""
    e_range = ERange(E_min=start, E_max=stop, E_step=step, exposure=0.1)
    np.testing.assert_allclose(e_range.energies(), expected_energies)
    np.testing.assert_allclose(e_range.exposures(), [0.1] * len(expected_energies))


def test_k_range():
    E0 = 17038
    k_range = KRange(k_min=2.8, k_max=14, k_step=0.05, k_weight=1, exposure=1.0)

    np.testing.assert_almost_equal(k_range.wavenumbers()[0], 2.8)
    np.testing.assert_almost_equal(k_range.wavenumbers()[-1], 14)
    energies = k_range.energies() + E0

    # Verify the results compared to Shelly's spreadsheet
    E_min = k_range.energies()[0]
    np.testing.assert_equal(energies[0], E0 + E_min)
    np.testing.assert_almost_equal(
        energies[-1], 746.7568692 + 17038, decimal=3
    )  # Athena value
    np.testing.assert_equal(k_range.exposures()[0], 1.0)
    np.testing.assert_almost_equal(k_range.exposures()[16], 1.28529317348436, decimal=3)


def test_merge_ranges():
    e_range1 = ERange(1, 5, 1, exposure=0.5)
    e_range2 = ERange(5, 7, 0.5, exposure=1)
    merged, exposures = merge_ranges(e_range2, e_range1)
    # Test validity of the result
    np.testing.assert_equal(merged, [1, 2, 3, 4, 5, 5.5, 6, 6.5, 7])
    np.testing.assert_equal(exposures, [0.5, 0.5, 0.5, 0.5, 1.0, 1.0, 1.0, 1.0, 1.0])


def test_merge_ranges_sorting():
    e_range1 = ERange(5, 7, 0.5, exposure=1)
    e_range2 = ERange(1, 5, 1, exposure=0.5)
    merged, exposures = merge_ranges(e_range2, e_range1, sort=True)
    # Test validity of the result
    np.testing.assert_equal(merged, [1, 2, 3, 4, 5, 5.5, 6, 6.5, 7])
    np.testing.assert_equal(exposures, [0.5, 0.5, 0.5, 0.5, 0.5, 1.0, 1.0, 1.0, 1.0])


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
