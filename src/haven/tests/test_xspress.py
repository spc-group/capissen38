import asyncio
from pathlib import Path

import pytest
from ophyd_async.core import TriggerInfo
from ophyd_async.testing import get_mock_put, set_mock_value

from haven.devices.detectors.xspress import Xspress3Detector

this_dir = Path(__file__).parent


@pytest.fixture()
async def detector():
    det = Xspress3Detector("255id_xsp:", name="vortex_me4")
    await det.connect(mock=True)
    set_mock_value(det.hdf.file_path_exists, True)
    return det


def test_mca_signals(detector):
    # Spot-check some PVs
    # print(list(detector.drv.children()))
    assert (
        detector.drv.acquire_time.source == "mock+ca://255id_xsp:det1:AcquireTime_RBV"
    )
    assert detector.drv.acquire.source == "mock+ca://255id_xsp:det1:Acquire_RBV"


async def test_trigger(detector):
    trigger_info = TriggerInfo(number_of_triggers=1)
    status = detector.trigger()
    await asyncio.sleep(0.1)  # Let the event loop turn
    set_mock_value(detector.hdf.num_captured, 1)
    await status
    # Check that signals were set
    get_mock_put(detector.drv.num_images).assert_called_once_with(1, wait=True)


async def test_stage(detector):
    assert not get_mock_put(detector.drv.erase).called
    await detector.stage()
    get_mock_put(detector.drv.erase_on_start).assert_called_once_with(False, wait=True)
    assert get_mock_put(detector.drv.erase).called


async def test_descriptor(detector):
    """There is a bug in the xspress3 EPICS driver that means it does not
    report the datatype correctly. This tests a workaround to decide
    based on the value of the dead_time_correction.

    https://github.com/epics-modules/xspress3/issues/57

    """
    # With deadtime correction off, we should get unsigned longs
    await detector.drv.deadtime_correction.set(False)
    assert await detector.writer._dataset_describer.np_datatype() == "<u4"
    # With deadtime correction on, we should get double-precision floats
    await detector.drv.deadtime_correction.set(True)
    assert await detector.writer._dataset_describer.np_datatype() == "<f8"


async def test_deadtime_correction(detector):
    """Deadtime correction in hardware is not reliable and should be
    disabled.

    https://github.com/epics-modules/xspress3/issues/57

    """
    set_mock_value(detector.drv.deadtime_correction, True)
    trigger_info = TriggerInfo(number_of_triggers=1)
    await detector.prepare(trigger_info)
    assert not await detector.drv.deadtime_correction.get_value()


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
