import pytest
from ophyd.utils.errors import ReadOnlyError
from ophyd_async.testing import get_mock_put, set_mock_value

from haven.devices.shutter import PssShutter, ShutterState


@pytest.fixture()
async def shutter(sim_registry):
    """
    Example PVs:

    S25ID-PSS:SCS:OpenEPICSC
    S25ID-PSS:SCS:CloseEPICSC
    S25ID-PSS:SCS:BeamBlockingM.VAL
    """
    shutter = PssShutter(prefix="S255ID-PSS:SCS:", name="shutter")
    await shutter.connect(mock=True)
    return shutter


async def test_read_shutter(shutter):
    """The current state of the shutter should be readable.

    This makes it compatible with the ``open_shutters_wrapper``.

    """
    reading = await shutter.read()
    assert shutter.name in reading


async def test_shutter_setpoint(shutter):
    """When we open and close the shutter, do the right EPICS signals get
    set?

    """
    # Prepare some mocking so we can operate properly
    open_put = get_mock_put(shutter.open_signal)
    close_put = get_mock_put(shutter.close_signal)
    set_mock_value(shutter.open_signal, 0)
    set_mock_value(shutter.close_signal, 0)
    # Close the shutter
    set_mock_value(shutter.open_signal, 0)
    set_mock_value(shutter.close_signal, 0)
    status = shutter.set(ShutterState.CLOSED)
    set_mock_value(shutter.readback, ShutterState.CLOSED)
    await status
    assert not open_put.called
    close_put.assert_called_once_with(1, wait=False)
    # Open the shutter
    open_put.reset_mock()
    close_put.reset_mock()
    set_mock_value(shutter.close_signal, 0)
    set_mock_value(shutter.open_signal, 0)
    status = shutter.set(ShutterState.OPEN)
    set_mock_value(shutter.readback, ShutterState.OPEN)
    await status
    assert not close_put.called
    open_put.assert_called_once_with(1, wait=False)


async def test_shutter_check_value(shutter):
    # Check for non-sense values
    with pytest.raises(ValueError):
        await shutter.set(ShutterState.FAULT)
    # Test shutter allow_close
    shutter.allow_close = False
    with pytest.raises(ReadOnlyError):
        await shutter.set(ShutterState.CLOSED)
    # Test shutter allow_open
    shutter.allow_open = False
    with pytest.raises(ReadOnlyError):
        await shutter.set(ShutterState.OPEN)


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
