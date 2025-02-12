import asyncio
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from ophyd_async.core import TriggerInfo
from ophyd_async.testing import get_mock_put, set_mock_value

from haven.devices.detectors.xspress import Xspress3Detector, ndattribute_params

this_dir = Path(__file__).parent


@pytest.fixture()
async def detector():
    det = Xspress3Detector("255id_xsp:", name="vortex_me4", elements=4)
    await det.connect(mock=True)
    set_mock_value(det.plugins["hdf"].file_path_exists, True)
    return det


async def test_signals(detector):
    assert await detector.ev_per_bin.get_value() == 10
    # Spot-check some PVs
    assert (
        detector.driver.acquire_time.source
        == "mock+ca://255id_xsp:det1:AcquireTime_RBV"
    )
    assert detector.driver.acquire.source == "mock+ca://255id_xsp:det1:Acquire_RBV"
    # Individual element's signals
    assert len(detector.elements) == 4
    elem0 = detector.elements[0]
    assert elem0.spectrum.source == "mock+ca://255id_xsp:MCA1:ArrayData"
    assert elem0.dead_time_percent.source == "mock+ca://255id_xsp:C1SCA:10:Value_RBV"
    assert elem0.dead_time_factor.source == "mock+ca://255id_xsp:C1SCA:9:Value_RBV"


async def test_description(detector):
    config = await detector.read_configuration()
    assert f"{detector.name}-ev_per_bin" in config


@pytest.mark.asyncio
async def test_trigger(detector):
    status = detector.trigger()
    await asyncio.sleep(0.1)  # Let the event loop turn
    set_mock_value(detector.plugins["hdf"].num_captured, 1)
    await status
    # Check that signals were set
    get_mock_put(detector.driver.num_images).assert_called_once_with(1, wait=True)


async def test_stage(detector):
    assert not get_mock_put(detector.driver.erase).called
    await detector.stage()
    get_mock_put(detector.driver.erase_on_start).assert_called_once_with(
        False, wait=True
    )
    assert get_mock_put(detector.driver.erase).called


async def test_descriptor(detector):
    """There is a bug in the xspress3 EPICS driver that means it does not
    report the datatype correctly. This tests a workaround to decide
    based on the value of the dead_time_correction.

    https://github.com/epics-modules/xspress3/issues/57

    """
    # With deadtime correction off, we should get unsigned longs
    await detector.driver.deadtime_correction.set(False)
    assert await detector._writer._dataset_describer.np_datatype() == "<u4"
    # With deadtime correction on, we should get double-precision floats
    await detector.driver.deadtime_correction.set(True)
    assert await detector._writer._dataset_describer.np_datatype() == "<f8"


async def test_deadtime_correction_disabled(detector):
    """Deadtime correction in hardware is not reliable and should be
    disabled.

    https://github.com/epics-modules/xspress3/issues/57

    """
    set_mock_value(detector.driver.deadtime_correction, True)
    trigger_info = TriggerInfo(number_of_triggers=1)
    await detector.prepare(trigger_info)
    assert not await detector.driver.deadtime_correction.get_value()


def test_default_time_signal_xspress(xspress):
    # assert xspress.default_time_signal is xspress.acquire_time
    assert xspress.default_time_signal is xspress.driver.acquire_time


async def test_ndattribute_params():
    n_elem = 8
    n_params = 1
    params = ndattribute_params(device_name="xsp3", elements=range(n_elem))
    assert len(params) == n_elem * n_params


async def test_stage_ndattributes(detector):
    num_elem = 8
    set_mock_value(detector.driver.number_of_elements, num_elem)
    set_mock_value(detector.driver.nd_attributes_file, "XSP3.xml")
    num_params = 1
    await detector.stage()
    xml_mock = get_mock_put(detector.driver.nd_attributes_file)
    assert xml_mock.called
    # Test that the XML is correct
    args, kwargs = xml_mock.call_args
    tree = ET.fromstring(args[0])
    assert len(tree) == num_elem * num_params
    # Check that the XML file gets reset when unstaged
    await detector.unstage()
    assert xml_mock.call_args[0][0] == "XSP3.xml"


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
