import logging
from enum import IntEnum

from apstools.devices import CamMixin_V34, SingleTrigger_V34
from ophyd import ADComponent as ADCpt
from ophyd import DetectorBase as OphydDetectorBase
from ophyd import (
    EigerDetectorCam,
    Kind,
    Lambda750kCam,
    OphydObject,
    SimDetectorCam,
    SingleTrigger,
)
from ophyd.areadetector.base import EpicsSignalWithRBV as SignalWithRBV
from ophyd.areadetector.filestore_mixins import FileStoreHDF5IterativeWrite
from ophyd.areadetector.plugins import (
    HDF5Plugin_V31,
    HDF5Plugin_V34,
    ImagePlugin_V31,
    ImagePlugin_V34,
    OverlayPlugin,
    PvaPlugin_V31,
    PvaPlugin_V34,
    ROIPlugin_V31,
    ROIPlugin_V34,
)
from ophyd.areadetector.plugins import StatsPlugin_V31 as OphydStatsPlugin_V31
from ophyd.areadetector.plugins import StatsPlugin_V34 as OphydStatsPlugin_V34
from ophyd.areadetector.plugins import TIFFPlugin_V31

from .. import exceptions
from .._iconfig import load_config
from .device import make_device

log = logging.getLogger(__name__)


__all__ = ["Eiger500K", "Lambda250K", "SimDetector", "AsyncCamMixin"]


class AsyncCamMixin(OphydObject):
    """A mixin that allows for delayed evaluation of the connection status.

    Ordinarily, and area detector gets the camera acquire signal,
    which requires that it be connected. With this mixin, you can skip
    that step, so that you can ``wait_for_connection()`` fully at a
    later time.

    """

    lazy_wait_for_connection = False

    # Components
    acquire = ADCpt(SignalWithRBV, "Acquire")


class SimDetectorCam_V34(CamMixin_V34, SimDetectorCam): ...


class EigerCam(AsyncCamMixin, EigerDetectorCam): ...


class LambdaCam(AsyncCamMixin, Lambda750kCam): ...


class WriteModes(IntEnum):
    SINGLE = 0
    CAPTURE = 1
    STREAM = 2


class Capture(IntEnum):
    STOP = 0
    START = 1


class StageCapture:
    """Mixin to prepare NDPlugin file capture mode.

    Sets the number of captures to zero (infinite), and starts
    capturing. Then when the device gets unstaged, capturing turns
    back off.

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Stage the capture button as well
        self.stage_sigs[self.file_write_mode] = WriteModes.STREAM
        self.stage_sigs[self.capture] = Capture.START
        self.stage_sigs[self.num_capture] = 0


class MyHDF5Plugin(FileStoreHDF5IterativeWrite, HDF5Plugin_V34):
    """
    Add data acquisition methods to HDF5Plugin.
    * ``stage()`` - prepare device PVs befor data acquisition
    * ``unstage()`` - restore device PVs after data acquisition
    * ``generate_datum()`` - coordinate image storage metadata
    """

    def stage(self):
        self.stage_sigs.move_to_end("capture", last=True)
        super().stage()


class DetectorBase(OphydDetectorBase):
    def __init__(self, *args, description=None, **kwargs):
        super().__init__(*args, **kwargs)
        if description is None:
            description = self.name
        self.description = description

    @property
    def default_time_signal(self):
        return self.cam.acquire_time


class StatsMixin:
    overlays = ADCpt(OverlayPlugin, "Over1:")
    _default_read_attrs = [
        "max_value",
        "min_value",
        "min_xy.x",
        "max_xy.x",
        "min_xy.y",
        "max_xy.y",
        "total",
        "net",
        "mean_value",
        "sigma_value",
    ]


class StatsPlugin_V31(StatsMixin, OphydStatsPlugin_V31): ...


class StatsPlugin_V34(StatsMixin, OphydStatsPlugin_V34): ...


class SimDetector(SingleTrigger_V34, DetectorBase):
    """
    ADSimDetector
    SingleTrigger:
    * stop any current acquisition
    * sets image_mode to 'Multiple'
    """

    cam = ADCpt(SimDetectorCam_V34, "cam1:")
    image = ADCpt(ImagePlugin_V34, "image1:")
    pva = ADCpt(PvaPlugin_V34, "Pva1:")
    hdf1 = ADCpt(
        type("HDF5Plugin", (StageCapture, HDF5Plugin_V34), {}),
        "HDF1:",
        # write_path_template="/tmp/",
        # read_path_template=READ_PATH_TEMPLATE,
    )
    roi1 = ADCpt(ROIPlugin_V34, "ROI1:", kind=Kind.config)
    roi2 = ADCpt(ROIPlugin_V34, "ROI2:", kind=Kind.config)
    roi3 = ADCpt(ROIPlugin_V34, "ROI3:", kind=Kind.config)
    roi4 = ADCpt(ROIPlugin_V34, "ROI4:", kind=Kind.config)
    stats1 = ADCpt(StatsPlugin_V34, "Stats1:", kind=Kind.normal)
    stats2 = ADCpt(StatsPlugin_V34, "Stats2:", kind=Kind.normal)
    stats3 = ADCpt(StatsPlugin_V34, "Stats3:", kind=Kind.normal)
    stats4 = ADCpt(StatsPlugin_V34, "Stats4:", kind=Kind.normal)
    stats5 = ADCpt(StatsPlugin_V34, "Stats5:", kind=Kind.normal)


class TIFFPlugin(StageCapture, TIFFPlugin_V31):
    _default_read_attrs = ["full_file_name"]


class HDF5Plugin(StageCapture, HDF5Plugin_V31):
    _default_read_attrs = ["full_file_name"]


class Lambda250K(SingleTrigger, DetectorBase):
    """
    A Lambda 250K area detector device.
    """

    cam = ADCpt(LambdaCam, "cam1:")
    image = ADCpt(ImagePlugin_V31, "image1:")
    pva = ADCpt(PvaPlugin_V31, "Pva1:")
    tiff = ADCpt(TIFFPlugin, "TIFF1:", kind=Kind.normal)
    hdf1 = ADCpt(HDF5Plugin, "HDF1:", kind=Kind.normal)
    roi1 = ADCpt(ROIPlugin_V31, "ROI1:", kind=Kind.config)
    roi2 = ADCpt(ROIPlugin_V31, "ROI2:", kind=Kind.config)
    roi3 = ADCpt(ROIPlugin_V31, "ROI3:", kind=Kind.config)
    roi4 = ADCpt(ROIPlugin_V31, "ROI4:", kind=Kind.config)
    stats1 = ADCpt(StatsPlugin_V31, "Stats1:", kind=Kind.normal)
    stats2 = ADCpt(StatsPlugin_V31, "Stats2:", kind=Kind.normal)
    stats3 = ADCpt(StatsPlugin_V31, "Stats3:", kind=Kind.normal)
    stats4 = ADCpt(StatsPlugin_V31, "Stats4:", kind=Kind.normal)
    stats5 = ADCpt(StatsPlugin_V31, "Stats5:", kind=Kind.normal)

    _default_read_attrs = [
        "stats1",
        "stats2",
        "stats3",
        "stats4",
        "stats5",
        "hdf1",
        "tiff",
    ]


class Eiger500K(SingleTrigger, DetectorBase):
    """
    A Eiger S 500K area detector device.
    """

    cam = ADCpt(EigerCam, "cam1:")
    image = ADCpt(ImagePlugin_V34, "image1:")
    pva = ADCpt(PvaPlugin_V34, "Pva1:")
    tiff = ADCpt(TIFFPlugin, "TIFF1:", kind=Kind.normal)
    hdf1 = ADCpt(HDF5Plugin, "HDF1:", kind=Kind.normal)
    roi1 = ADCpt(ROIPlugin_V34, "ROI1:", kind=Kind.config)
    roi2 = ADCpt(ROIPlugin_V34, "ROI2:", kind=Kind.config)
    roi3 = ADCpt(ROIPlugin_V34, "ROI3:", kind=Kind.config)
    roi4 = ADCpt(ROIPlugin_V34, "ROI4:", kind=Kind.config)
    stats1 = ADCpt(StatsPlugin_V34, "Stats1:", kind=Kind.normal)
    stats2 = ADCpt(StatsPlugin_V34, "Stats2:", kind=Kind.normal)
    stats3 = ADCpt(StatsPlugin_V34, "Stats3:", kind=Kind.normal)
    stats4 = ADCpt(StatsPlugin_V34, "Stats4:", kind=Kind.normal)
    stats5 = ADCpt(StatsPlugin_V34, "Stats5:", kind=Kind.normal)

    _default_read_attrs = [
        "stats1",
        "stats2",
        "stats3",
        "stats4",
        "stats5",
        "hdf1",
        "tiff",
    ]


def load_area_detectors(config=None) -> set:
    if config is None:
        config = load_config()
    # Create the area detectors defined in the configuration
    devices = []
    for name, adconfig in config.get("area_detector", {}).items():
        DeviceClass = globals().get(adconfig["device_class"])
        # Check that it's a valid device class
        if DeviceClass is None:
            msg = f"area_detector.{name}.device_class={adconfig['device_class']}"
            raise exceptions.UnknownDeviceConfiguration(msg)
        # Create the device co-routine
        devices.append(
            make_device(
                DeviceClass,
                prefix=f"{adconfig['prefix']}:",
                name=name,
                labels={"area_detectors", "detectors"},
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
