import numpy as np
import pytest
from ophyd.sim import det1, det2, motor1

from haven.plans._beam_properties import fit_step, knife_scan


# @pytest.mark.xfail()
def test_fit_step():
    # Data taken from 25-ID-C scan 927fa7dd-e331-45ca-bb9d-3f89d7c65b17
    x = np.asarray(
        [
            4000.0,
            4098.75,
            4196.25,
            4295.0,
            4393.75,
            4491.25,
            4590.0,
            4688.75,
            4787.5,
            4885.0,
            4983.75,
            5082.5,
            5180.0,
            5278.75,
            5377.5,
            5475.0,
            5573.75,
            5672.5,
            5770.0,
            5868.75,
            5967.5,
            6065.0,
            6163.75,
            6262.5,
            6361.25,
            6458.75,
            6557.5,
            6656.25,
            6753.75,
            6852.5,
            6951.25,
            7048.75,
            7147.5,
            7246.25,
            7343.75,
            7442.5,
            7541.25,
            7638.75,
            7737.5,
            7836.25,
            7935.0,
            8032.5,
            8131.25,
            8230.0,
            8327.5,
            8426.25,
            8525.0,
            8622.5,
            8721.25,
            8820.0,
            8917.5,
            9016.25,
            9115.0,
            9212.5,
            9311.25,
            9410.0,
            9508.75,
            9606.25,
            9705.0,
            9803.75,
            9901.25,
            10000.0,
        ]
    )
    y = np.asarray(
        [
            1986948.0,
            1986762.0,
            1986219.0,
            1985857.0,
            1986368.0,
            1988565.0,
            1984304.0,
            1984083.0,
            1984260.0,
            1977423.0,
            1962293.0,
            1934651.0,
            1893159.0,
            1831347.0,
            1744330.0,
            1637858.0,
            1518247.0,
            1383126.0,
            1251727.0,
            1112157.0,
            977554.0,
            845534.0,
            712432.0,
            582380.0,
            457525.0,
            347780.0,
            248174.0,
            166589.0,
            105856.0,
            66173.0,
            39880.0,
            24760.0,
            16304.0,
            11544.0,
            8930.0,
            7215.0,
            6162.0,
            5401.0,
            5077.0,
            4828.0,
            4620.0,
            4433.0,
            4257.0,
            4122.0,
            3988.0,
            3886.0,
            3799.0,
            3711.0,
            3622.0,
            3505.0,
            3434.0,
            3392.0,
            3369.0,
            3368.0,
            3307.0,
            3309.0,
            3295.0,
            3266.0,
            3290.0,
            3218.0,
            3193.0,
            3147.0,
        ]
    )
    expected_center = 5960.94  # 5961.21
    # Do the fitting
    result = fit_step(x, y, plot=False, plot_derivative=False)
    assert result.position == pytest.approx(expected_center)
    assert result.fwhm == pytest.approx(1449.956)


def test_knife_scan():
    plan = knife_scan(motor1, -200, 200, 401, I0=det1, It=det2, relative=True)
    # Check metadata
    open_msg = [m for m in plan if m.command == "open_run"][0]
    assert open_msg.kwargs["plan_name"] == "knife_scan"
    assert open_msg.kwargs["num_points"] == 401


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
