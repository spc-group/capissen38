from unittest import mock

import numpy as np
import pydm
import pyqtgraph
import pytest
from PyQt5.QtCore import Qt

from firefly.area_detector_viewer import AreaDetectorViewerDisplay


@pytest.fixture()
def display(qtbot, sim_camera):
    display = AreaDetectorViewerDisplay(macros={"AD": sim_camera.name})
    qtbot.addWidget(display)
    return display


def test_image_plotting(display):
    assert isinstance(display.image_view, pyqtgraph.ImageView)
    assert isinstance(display.image_channel, pydm.PyDMChannel)
    # Give it some grayscale data
    source_img = np.random.randint(0, 256, size=(54, 64))
    # For some reason, PyDMConnection mis-shapes the data
    reshape_img = np.reshape(source_img, source_img.shape[::-1])
    display.image_channel.value_slot(reshape_img)
    # See if we get a plottable image out
    new_image = display.image_view.getImageItem()
    assert new_image.image is not None
    assert new_image.image.shape == (54, 64)
    np.testing.assert_equal(new_image.image, source_img)
    # Give it some RGB data
    source_img = np.random.randint(0, 256, size=(54, 64, 3))
    # For some reason, PyDMConnection mis-shapes the data
    reshape_img = np.reshape(source_img, source_img.shape[::-1])
    display.image_channel.value_slot(reshape_img)
    # See if we get a plottable image out
    new_image = display.image_view.getImageItem()
    assert new_image.image.shape == (54, 64, 3)
    display.image_channel.disconnect()


def test_caqtdm_window(display, sim_camera):
    display._open_caqtdm_subprocess = mock.MagicMock()
    # Launch the caqtdm display
    display.launch_caqtdm()
    display._open_caqtdm_subprocess.assert_called_once_with(
        f"start_{sim_camera.prefix}_caqtdm"
    )


def test_exposure_checkbox_push_button(display, qtbot):
    """
    Test the interaction between the Exposure checkbox and push button.
    """
    exposure_checkbox = display.exposure_checkbox
    exposure_push_button = display.exposure_push_button

    # Initially both should be enabled
    assert exposure_checkbox.isEnabled()
    assert exposure_push_button.isEnabled()

    # Simulate checking the checkbox
    exposure_checkbox.setChecked(True)
    assert (
        not exposure_push_button.isEnabled()
    ), "Exposure PushButton should be disabled when Checkbox is checked."

    # Simulate unchecking the checkbox
    exposure_checkbox.setChecked(False)
    assert (
        exposure_push_button.isEnabled()
    ), "Exposure PushButton should be enabled when Checkbox is unchecked."

    # Simulate clicking the push button
    qtbot.mouseClick(exposure_push_button, Qt.LeftButton)
    assert (
        not exposure_checkbox.isChecked()
    ), "Exposure Checkbox should be unchecked when PushButton is clicked."


def test_gain_checkbox_push_button(display, qtbot):
    """
    Test the interaction between the Gain checkbox and push button.
    """
    gain_checkbox = display.gain_checkbox
    gain_push_button = display.gain_push_button

    # Initially both should be enabled
    assert gain_checkbox.isEnabled()
    assert gain_push_button.isEnabled()

    # Simulate checking the checkbox
    gain_checkbox.setChecked(True)
    assert (
        not gain_push_button.isEnabled()
    ), "Gain PushButton should be disabled when Checkbox is checked."

    # Simulate unchecking the checkbox
    gain_checkbox.setChecked(False)
    assert (
        gain_push_button.isEnabled()
    ), "Gain PushButton should be enabled when Checkbox is unchecked."

    # Simulate clicking the push button
    qtbot.mouseClick(gain_push_button, Qt.LeftButton)
    assert (
        not gain_checkbox.isChecked()
    ), "Gain Checkbox should be unchecked when PushButton is clicked."


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
