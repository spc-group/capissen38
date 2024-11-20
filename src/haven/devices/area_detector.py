import logging
import time
import warnings
from collections import OrderedDict, namedtuple
from enum import IntEnum
from typing import Dict, Mapping

import numpy as np
import pandas as pd
from apstools.devices import CamMixin_V34, SingleTrigger_V34
from ophyd import ADComponent as ADCpt
from ophyd import CamBase
from ophyd import Component as Cpt
from ophyd import DetectorBase as OphydDetectorBase
from ophyd import (
    Device,
    EigerDetectorCam,
    EpicsSignal,
    Kind,
    Lambda750kCam,
    OphydObject,
    Signal,
    SimDetectorCam,
    SingleTrigger,
)
from ophyd.areadetector.base import EpicsSignalWithRBV as SignalWithRBV
from ophyd.areadetector.filestore_mixins import (
    FileStoreHDF5IterativeWrite,
    FileStoreTIFFIterativeWrite,
)
from ophyd.areadetector.plugins import (
    HDF5Plugin_V31,
    HDF5Plugin_V34,
    ImagePlugin_V31,
    ImagePlugin_V34,
    OverlayPlugin,
    OverlayPlugin_V34,
    PvaPlugin_V31,
    PvaPlugin_V34,
    ROIPlugin_V31,
    ROIPlugin_V34,
)
from ophyd.areadetector.plugins import StatsPlugin_V31 as OphydStatsPlugin_V31
from ophyd.areadetector.plugins import StatsPlugin_V34 as OphydStatsPlugin_V34
from ophyd.areadetector.plugins import TIFFPlugin_V31, TIFFPlugin_V34
from ophyd.flyers import FlyerInterface
from ophyd.sim import make_fake_device
from ophyd.status import Status, StatusBase, SubscriptionStatus

from .. import exceptions
from .._iconfig import load_config

log = logging.getLogger(__name__)


__all__ = ["Eiger500K", "Lambda250K", "SimDetector", "AsyncCamMixin"]


class WriteModes(IntEnum):
    SINGLE = 0
    CAPTURE = 1
    STREAM = 2


class Capture(IntEnum):
    STOP = 0
    START = 1


class ImageMode(IntEnum):
    SINGLE = 0
    MULTIPLE = 1
    CONTINUOUS = 2


class EraseState(IntEnum):
    DONE = 0
    ERASE = 1


class AcquireState(IntEnum):
    DONE = 0
    ACQUIRE = 1


class TriggerMode(IntEnum):
    SOFTWARE = 0
    INTERNAL = 1
    IDC = 2
    TTL_VETO_ONLY = 3
    TTL_BOTH = 4
    LVDS_VETO_ONLY = 5
    LVDS_BOTH = 6


class DetectorState(IntEnum):
    IDLE = 0
    ACQUIRE = 1
    READOUT = 2
    CORRECT = 3
    SAVING = 4
    ABORTING = 5
    ERROR = 6
    WAITING = 7
    INITIALIZING = 8
    DISCONNECTED = 9
    ABORTED = 10


fly_event = namedtuple("fly_event", ("timestamp", "value"))


class FlyerMixin(FlyerInterface, Device):
    flyer_num_points = Cpt(Signal)
    flyscan_trigger_mode = TriggerMode.SOFTWARE

    def save_fly_datum(self, *, value, timestamp, obj, **kwargs):
        """Callback to save data from a signal during fly-scanning."""
        datum = fly_event(timestamp=timestamp, value=value)
        self._fly_data.setdefault(obj, []).append(datum)

    def kickoff(self) -> StatusBase:
        # Set up subscriptions for capturing data
        self._fly_data = {}
        for walk in self.walk_fly_signals():
            sig = walk.item
            # Run subs the first time to make sure all signals are present
            sig.subscribe(self.save_fly_datum, run=True)

        # Set up the status for when the detector is ready to fly
        def check_acquiring(*, old_value, value, **kwargs):
            is_acquiring = value == DetectorState.ACQUIRE
            if is_acquiring:
                self.start_fly_timestamp = time.time()
            return is_acquiring

        status = SubscriptionStatus(self.cam.detector_state, check_acquiring)
        # Set the right parameters
        self._original_vals.setdefault(self.cam.image_mode, self.cam.image_mode.get())
        status &= self.cam.image_mode.set(ImageMode.CONTINUOUS)
        status &= self.cam.trigger_mode.set(self.flyscan_trigger_mode)
        status &= self.cam.num_images.set(2**14)
        status &= self.cam.acquire.set(AcquireState.ACQUIRE)
        return status

    def complete(self) -> StatusBase:
        """Wait for flying to be complete.

        This commands the Xspress to stop acquiring fly-scan data.

        Returns
        -------
        complete_status : StatusBase
          Indicate when flying has completed
        """
        # Remove subscriptions for capturing fly-scan data
        for walk in self.walk_fly_signals():
            sig = walk.item
            sig.clear_sub(self.save_fly_datum)
        self.cam.acquire.set(AcquireState.DONE)
        return Status(done=True, success=True, settle_time=0.5)

    def collect(self) -> dict:
        """Generate the data events that were collected during the fly scan."""
        # Load the collected data, and get rid of extras
        fly_data, fly_ts = self.fly_data()
        fly_data.drop("timestamps", inplace=True, axis="columns")
        fly_ts.drop("timestamps", inplace=True, axis="columns")
        # Yield each row one at a time
        for data_row, ts_row in zip(fly_data.iterrows(), fly_ts.iterrows()):
            payload = {
                "data": {sig.name: val for (sig, val) in data_row[1].items()},
                "timestamps": {sig.name: val for (sig, val) in ts_row[1].items()},
                "time": float(np.median(np.unique(ts_row[1].values))),
            }
            yield payload

    def describe_collect(self) -> Dict[str, Dict]:
        """Describe details for the flyer collect() method"""
        desc = OrderedDict()
        # for walk in self.walk_fly_signals():
        #     desc.update(walk.item.describe())
        return {self.name: self.describe()}

    def fly_data(self):
        """Compile the fly-scan data into a pandas dataframe."""
        # Get the data for frame number as a reference
        image_counter = pd.DataFrame(
            self._fly_data[self.cam.array_counter],
            columns=["timestamps", "image_counter"],
        )
        image_counter["image_counter"] -= 2  # Correct for stray frames
        # Build all the individual signals' dataframes
        dfs = []
        for sig, data in self._fly_data.items():
            df = pd.DataFrame(data, columns=["timestamps", sig])
            old_shape = df.shape
            nums = (df.timestamps - image_counter.timestamps).abs()

            # Assign each datum an image number based on timestamp
            def get_image_num(ts):
                """Get the image number taken closest to a given timestamp."""
                num = image_counter.iloc[
                    (image_counter["timestamps"] - ts).abs().argsort()[:1]
                ]
                num = num["image_counter"].iloc[0]
                return num

            im_nums = [get_image_num(ts) for ts in df.timestamps.values]
            df.index = im_nums
            # Remove duplicates and intermediate ROI sums
            df.sort_values("timestamps")
            df = df.groupby(df.index).last()
            dfs.append(df)
        # Combine frames into monolithic dataframes
        data = image_counter.copy()
        data = data.set_index("image_counter", drop=True)
        timestamps = data.copy()
        for df in dfs:
            sig = df.columns[1]
            data[sig] = df[sig]
            timestamps[sig] = df["timestamps"]
        # Fill in missing values, most likely because the value didn't
        # change so no new camonitor reply was received
        data = data.ffill(axis=0)
        timestamps = timestamps.ffill(axis=1)
        # Drop the first frame since it was just the result of all the subs
        data.drop(data.index[0], inplace=True)
        timestamps.drop(timestamps.index[0], inplace=True)
        return data, timestamps

    def walk_fly_signals(self, *, include_lazy=False):
        """Walk all signals in the Device hierarchy that are to be read during
        fly-scanning.

        Parameters
        ----------
        include_lazy : bool, optional
            Include not-yet-instantiated lazy signals

        Yields
        ------
        ComponentWalk
            Where ancestors is all ancestors of the signal, including the
            top-level device `walk_signals` was called on.

        """
        for walk in self.walk_signals():
            # Image counter has to be included for data alignment
            if walk.item is self.cam.array_counter:
                yield walk
                continue
            # Only include readable signals
            if not bool(walk.item.kind & Kind.normal):
                continue
            # ROI sums do not get captured properly during flying
            # Instead, they should be calculated at the end
            # if self.roi_sums in walk.ancestors:
            #     continue
            yield walk


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


class SingleImageModeTrigger(SingleTrigger_V34):
    """A trigger mixin for cameras that don't support "Multiple" image mode."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "cam.image_mode" in self.stage_sigs:
            self.stage_sigs["cam.image_mode"] = ImageMode.SINGLE


class SimDetectorCam_V34(CamMixin_V34, SimDetectorCam): ...


class EigerCam(AsyncCamMixin, EigerDetectorCam): ...


class LambdaCam(AsyncCamMixin, Lambda750kCam): ...


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


class DynamicFileStore(Device):
    """File store mixin that alters the write_path_template based on
    iconfig values.

    """

    def __init__(
        self, *args, write_path_template="/{root_path}/%Y/%m/{name}/", **kwargs
    ):
        super().__init__(*args, write_path_template=write_path_template, **kwargs)
        # Format the file_write_template with per-device values
        config = load_config()
        root_path = config.get("area_detector_root_path", "tmp")
        # Remove the leading slash for some reason...makes ophyd happy
        root_path = root_path.lstrip("/")
        try:
            
            self.write_path_template = self.write_path_template.format(
                name=self.parent.name,
                root_path=root_path,
            )
        except KeyError:
            warnings.warn(f"Could not format write_path_template {write_path_template}")

    def _add_dtype_str(self, desc: Mapping) -> Mapping:
        """Add the specific image data type into the metadata.

        This method modifies the dictionary in place.

        Parameters
        ==========
        desc:
          The input description, most likely coming from self.describe().

        Returns
        =======
        desc
          The same dictionary, with an added ``dtype_str`` key.

        """
        key = f"{self.parent.name}_image"
        if key in desc:
            dtype = self.data_type.get(as_string=True)
            dtype_str = np.dtype(dtype.lower()).str
            desc[key].setdefault("dtype_str", dtype_str)
        return desc

    def describe(self):
        return self._add_dtype_str(super().describe())


class HDF5FilePlugin(DynamicFileStore, FileStoreHDF5IterativeWrite, HDF5Plugin_V34):
    """
    Add data acquisition methods to HDF5Plugin.
    * ``stage()`` - prepare device PVs befor data acquisition
    * ``unstage()`` - restore device PVs after data acquisition
    * ``generate_datum()`` - coordinate image storage metadata
    """

    def stage(self):
        self.stage_sigs.move_to_end("capture", last=True)
        super().stage()


class TIFFFilePlugin(DynamicFileStore, FileStoreTIFFIterativeWrite, TIFFPlugin_V34): ...


class DetectorBase(FlyerMixin, OphydDetectorBase):
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
        HDF5FilePlugin,
        "HDF1:",
        write_path_template="/tmp/",
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
    overlays = ADCpt(OverlayPlugin_V34, "Over1:")


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
    # tiff = ADCpt(TIFFPlugin, "TIFF1:", kind=Kind.normal)
    hdf = ADCpt(HDF5FilePlugin, "HDF1:", kind=Kind.normal)
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
        "hdf",
        # "tiff",
    ]


class AravisCam(AsyncCamMixin, CamBase):
    gain_auto = ADCpt(EpicsSignal, "GainAuto")
    acquire_time_auto = ADCpt(EpicsSignal, "ExposureAuto")


class AravisDetector(SingleImageModeTrigger, DetectorBase):
    """
    A gige-vision camera described by EPICS.
    """

    _default_configuration_attrs = (
        "cam",
        "hdf",
        "stats1",
        "stats2",
        "stats3",
        "stats4",
    )
    _default_read_attrs = ("cam", "hdf", "stats1", "stats2", "stats3", "stats4")

    cam = ADCpt(AravisCam, "cam1:")
    image = ADCpt(ImagePlugin_V34, "image1:")
    pva = ADCpt(PvaPlugin_V34, "Pva1:")
    overlays = ADCpt(OverlayPlugin_V34, "Over1:")
    roi1 = ADCpt(ROIPlugin_V34, "ROI1:", kind=Kind.config)
    roi2 = ADCpt(ROIPlugin_V34, "ROI2:", kind=Kind.config)
    roi3 = ADCpt(ROIPlugin_V34, "ROI3:", kind=Kind.config)
    roi4 = ADCpt(ROIPlugin_V34, "ROI4:", kind=Kind.config)
    stats1 = ADCpt(StatsPlugin_V34, "Stats1:", kind=Kind.normal)
    stats2 = ADCpt(StatsPlugin_V34, "Stats2:", kind=Kind.normal)
    stats3 = ADCpt(StatsPlugin_V34, "Stats3:", kind=Kind.normal)
    stats4 = ADCpt(StatsPlugin_V34, "Stats4:", kind=Kind.normal)
    stats5 = ADCpt(StatsPlugin_V34, "Stats5:", kind=Kind.normal)
    hdf = ADCpt(HDF5FilePlugin, "HDF1:", kind=Kind.normal)
    # tiff = ADCpt(TIFFFilePlugin, "TIFF1:", kind=Kind.normal)


def make_area_detector(prefix: str, name: str, device_class: str, mock=True) -> Device:
    # Create the area detectors defined in the configuration
    try:
        DeviceClass = globals().get(device_class)
    except TypeError:
        msg = f"area_detector.{name}.device_class={device_class}"
        raise exceptions.UnknownDeviceConfiguration(msg)
    # Create a simulated version if needed
    if mock:
        DeviceClass = make_fake_device(DeviceClass)
    # Create the device co-routine
    device = DeviceClass(
        prefix=prefix,
        name=name,
        labels={"area_detectors", "detectors"},
    )
    return device


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
