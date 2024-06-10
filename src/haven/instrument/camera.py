import logging
from typing import Sequence

from ophyd import ADComponent as ADCpt
from ophyd import CamBase, EpicsSignal, Kind, SingleTrigger
from ophyd.areadetector.plugins import (
    ImagePlugin_V34,
    OverlayPlugin,
    PvaPlugin_V34,
    ROIPlugin_V34,
)

from .. import exceptions
from .._iconfig import load_config
from .area_detector import (  # noqa: F401
    AsyncCamMixin,
    DetectorBase,
    SimDetector,
    StatsPlugin_V34,
)
from .device import make_device

log = logging.getLogger(__name__)


__all__ = ["AravisDetector", "load_cameras"]


class AravisCam(AsyncCamMixin, CamBase):
    gain_auto = ADCpt(EpicsSignal, "GainAuto")
    acquire_time_auto = ADCpt(EpicsSignal, "ExposureAuto")


class AravisDetector(SingleTrigger, DetectorBase):
    """
    A gige-vision camera described by EPICS.
    """

    cam = ADCpt(AravisCam, "cam1:")
    image = ADCpt(ImagePlugin_V34, "image1:")
    pva = ADCpt(PvaPlugin_V34, "Pva1:")
    overlays = ADCpt(OverlayPlugin, "Over1:")
    roi1 = ADCpt(ROIPlugin_V34, "ROI1:", kind=Kind.config)
    roi2 = ADCpt(ROIPlugin_V34, "ROI2:", kind=Kind.config)
    roi3 = ADCpt(ROIPlugin_V34, "ROI3:", kind=Kind.config)
    roi4 = ADCpt(ROIPlugin_V34, "ROI4:", kind=Kind.config)
    stats1 = ADCpt(StatsPlugin_V34, "Stats1:", kind=Kind.normal)
    stats2 = ADCpt(StatsPlugin_V34, "Stats2:", kind=Kind.normal)
    stats3 = ADCpt(StatsPlugin_V34, "Stats3:", kind=Kind.normal)
    stats4 = ADCpt(StatsPlugin_V34, "Stats4:", kind=Kind.normal)
    stats5 = ADCpt(StatsPlugin_V34, "Stats5:", kind=Kind.normal)


def load_cameras(config=None) -> Sequence[DetectorBase]:
    """Create co-routines for loading cameras from config files.

    Returns
    =======
    coros
      A set of co-routines that can be awaited to load the cameras.

    """
    if config is None:
        config = load_config()
    # Get configuration details for the cameras
    device_configs = {
        k: v
        for (k, v) in config["camera"].items()
        if hasattr(v, "keys") and "prefix" in v.keys()
    }
    # Load each camera
    devices = []
    for key, cam_config in device_configs.items():
        class_name = cam_config.get("device_class", "AravisDetector")
        camera_name = cam_config.get("name", key)
        description = cam_config.get("description", cam_config.get("name", key))
        DeviceClass = globals().get(class_name)
        # Check that it's a valid device class
        if DeviceClass is None:
            msg = f"camera.{key}.device_class={cam_config['device_class']}"
            raise exceptions.UnknownDeviceConfiguration(msg)
        # Create the device object
        devices.append(
            make_device(
                DeviceClass=DeviceClass,
                prefix=f"{cam_config['prefix']}:",
                name=camera_name,
                description=description,
                labels={"cameras"},
            )
        )
    return devices


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
