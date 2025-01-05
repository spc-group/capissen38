import pytest
from ophyd.sim import motor, motor1, motor2

from haven import exceptions
from haven.plans import set_energy


def test_plan_messages():
    """Check that the right messages are getting produced."""
    plan = set_energy(energy=8400, positioners=[motor])
    msgs = list(plan)
    assert len(msgs) == 2
    msg0 = msgs[0]
    assert msg0.args == (8400,)
    assert msg0.obj.name == "motor"


def test_id_harmonic():
    """See if messages get emitted to change the ID harmonic at
    certain intervals.

    """
    plan = set_energy(
        energy=8400, harmonic=3, positioners=[motor1], harmonic_positioners=[motor2]
    )
    msgs = list(plan)
    # Check that a message exists to the ID harmonic
    assert len(msgs) == 4
    msg0 = msgs[0]
    assert msg0.args == (3,)
    assert msg0.obj.name == "motor2"


def test_id_harmonic_auto():
    plan = set_energy(
        energy=8400,
        harmonic="auto",
        positioners=[motor1],
        harmonic_positioners=[motor2],
    )
    msgs = list(plan)
    # Check that a message exists to the ID harmonic
    assert len(msgs) == 4
    msg0 = msgs[0]
    assert msg0.args == (1,)
    assert msg0.obj.name == "motor2"
    # Try again but with a 3rd harmonic
    plan = set_energy(
        energy=18400,
        harmonic="auto",
        positioners=[motor1],
        harmonic_positioners=[motor2],
    )
    msgs = list(plan)
    # Check that a message exists to the ID harmonic
    assert len(msgs) == 4
    msg0 = msgs[0]
    assert msg0.args == (3,)
    assert msg0.obj.name == "motor2"


def test_invalid_harmonic():
    plan = set_energy(
        energy=8400,
        harmonic="jabberwocky",
        positioners=[motor1],
        harmonic_positioners=[motor2],
    )
    with pytest.raises(exceptions.InvalidHarmonic):
        list(plan)


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
