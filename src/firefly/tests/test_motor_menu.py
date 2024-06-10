import pytest
from ophyd.sim import make_fake_device

from firefly.main_window import FireflyMainWindow
from haven.instrument import motor


@pytest.fixture
def fake_motors(sim_registry):
    motor_names = ["motorA", "motorB", "motorC"]
    motors = []
    for name in motor_names:
        this_motor = make_fake_device(motor.HavenMotor)(
            name=name, labels={"extra_motors"}
        )
        motors.append(this_motor)
    return motors


def test_motor_menu(fake_motors, qtbot, ffapp):
    ffapp.setup_window_actions()
    ffapp.setup_runengine_actions()
    # Create the window
    window = FireflyMainWindow()
    # Check that the menu items have been created
    assert hasattr(window.ui, "positioners_menu")
    assert len(ffapp.motor_actions) == 3
    window.destroy()


def test_open_motor_window(fake_motors, monkeypatch, ffapp):
    # Set up the application
    ffapp.setup_window_actions()
    ffapp.setup_runengine_actions()
    # Simulate clicking on the menu action (they're in alpha order)
    action = ffapp.motor_actions["motorC"]
    action.trigger()
    # See if the window was created
    motor_3_name = "FireflyMainWindow_motor_motorC"
    assert motor_3_name in ffapp.windows.keys()
    macros = ffapp.windows[motor_3_name].display_widget().macros()
    assert macros["MOTOR"] == "motorC"


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
