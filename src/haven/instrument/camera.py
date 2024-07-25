import logging
from typing import Sequence, Mapping

from ophyd import ADComponent as ADCpt
from ophyd import CamBase, EpicsSignal, Kind
from ophyd.areadetector.plugins import (
    HDF5Plugin_V34,
    ImagePlugin_V34,
    OverlayPlugin_V34,
    PvaPlugin_V34,
    ROIPlugin_V34,
    TIFFPlugin_V34,
)
from ophyd_async.epics.adaravis import (
    AravisDetector as AravisDetectorBase,
    AravisDriverIO as AravisDriverIOBase,
    AravisController as AravisControllerBase,
)
from ophyd_async.core import YMDPathProvider, UUIDFilenameProvider, SubsetEnum
from ophyd_async.epics.signal import epics_signal_rw_rbv, epics_signal_r
from ophyd_async.epics.adcore import (
    NDFileHDFIO,
    ADHDFWriter,
    ADBaseShapeProvider,
    ADBaseDataType,
)

from .. import exceptions
from .._iconfig import load_config
from .area_detector import (  # noqa: F401
    AsyncCamMixin,
    DetectorBase,
    SimDetector,
    SingleImageModeTrigger,
    StatsPlugin_V34,
)
from .detectors.aravis import AravisDetector
from .device import make_device, connect_devices
from .instrument_registry import InstrumentRegistry
from .instrument_registry import registry as default_registry

log = logging.getLogger(__name__)


__all__ = ["load_cameras"]


async def load_cameras(
    config: Mapping = None, registry: InstrumentRegistry = default_registry
) -> Sequence[DetectorBase]:
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
            DeviceClass(
                prefix=f"{cam_config['prefix']}:",
                name=camera_name,
                # description=description,
                # labels={"cameras", "detectors"},
            )
        )
    # Connect to devices
    devices = await connect_devices(
        devices,
        labels={"cameras", "detectors"},
        mock=not config["beamline"]["is_connected"],
        registry=registry,
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
