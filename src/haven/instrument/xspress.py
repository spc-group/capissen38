import logging
import time
from collections import OrderedDict
from enum import IntEnum
from functools import partial
from typing import Dict, Optional, Sequence

import numpy as np
import pandas as pd
from apstools.devices import CamMixin_V34, SingleTrigger_V34
from ophyd import ADComponent as ADCpt
from ophyd import Component as Cpt
from ophyd import DetectorBase, Device
from ophyd import DynamicDeviceComponent as DDC
from ophyd import EpicsSignal, EpicsSignalRO, Kind
from ophyd.areadetector.base import EpicsSignalWithRBV as SignalWithRBV
from ophyd.signal import InternalSignal
from ophyd.status import StatusBase, SubscriptionStatus
from pcdsdevices.signal import MultiDerivedSignal
from pcdsdevices.type_hints import OphydDataType, SignalToValue

from .._iconfig import load_config
from .device import RegexComponent as RECpt
from .device import make_device
from .fluorescence_detector import (
    MCASumMixin,
    ROIMixin,
    UseROISignal,
    XRFMixin,
    add_roi_sums,
)

__all__ = ["load_xspress_detectors", "Xspress3Detector", "ROI"]


log = logging.getLogger(__name__)


active_kind = Kind.normal | Kind.config


NUM_ROIS = 16


class ChannelSignal(MultiDerivedSignal):
    """A high/low range limit channel for an ROI."""

    def set(
        self,
        value: OphydDataType,
        *,
        timeout: Optional[float] = None,
        settle_time: Optional[float] = None,
    ) -> StatusBase:
        # Check for existing signals and, if necessary, wait them out
        signals = [
            self.parent.hi_chan,
            self.parent.lo_chan,
            self.parent.size,
            self.parent._lo_chan,
        ]

        def get_threads():
            thds = [sig._set_thread for sig in signals if sig._set_thread]
            return [th for th in thds if th is not None]

        while len(threads := get_threads()) > 0:
            for th in threads:
                th.join()
        # Set the signal like normal
        return super().set(value, timeout=timeout, settle_time=settle_time)


class ROI(ROIMixin):
    def _get_hi_chan(self, mds: MultiDerivedSignal, items: SignalToValue) -> int:
        # Make sure other signals don't have pending threads
        lo = items[self._lo_chan]
        size = items[self.size]
        return lo + size

    def _put_hi_chan(
        self, mds: MultiDerivedSignal, value: OphydDataType
    ) -> SignalToValue:
        lo = self._lo_chan.get()
        new_size = value - lo
        return {self.size: new_size}

    def _get_lo_chan(self, mds: MultiDerivedSignal, items: SignalToValue) -> int:
        return items[self._lo_chan]

    def _put_lo_chan(
        self, mds: MultiDerivedSignal, value: OphydDataType
    ) -> SignalToValue:
        hi = self.hi_chan.get()
        return {
            self._lo_chan: value,
            self.size: hi - value,
        }

    label = Cpt(EpicsSignal, "Name", kind="config")
    _lo_chan = Cpt(EpicsSignal, "MinX", kind="omitted")
    size = Cpt(EpicsSignal, "SizeX", kind="config")
    hi_chan = Cpt(
        ChannelSignal,
        attrs=["_lo_chan", "size"],
        calculate_on_get=_get_hi_chan,
        calculate_on_put=_put_hi_chan,
    )
    lo_chan = Cpt(
        ChannelSignal,
        attrs=["_lo_chan", "size"],
        calculate_on_get=_get_lo_chan,
        calculate_on_put=_put_lo_chan,
    )
    background_width = Cpt(EpicsSignal, "BgdWidth", kind="config")
    use = Cpt(UseROISignal, derived_from="label", kind="config")

    count = Cpt(EpicsSignalRO, "Total_RBV", kind="normal")
    net_count = Cpt(EpicsSignalRO, "Net_RBV", kind="normal")
    min_count = Cpt(EpicsSignalRO, "MinValue_RBV", kind="normal")
    max_count = Cpt(EpicsSignalRO, "MaxValue_RBV", kind="normal")
    mean_count = Cpt(EpicsSignalRO, "MeanValue_RBV", kind="normal")

    _default_read_attrs = [
        "count",
        "net_count",
    ]
    _default_configuration_attrs = [
        "label",
        "background_width",
        "hi_chan",
        "lo_chan",
    ]
    kind = active_kind


def add_rois(
    range_: Sequence[int] = range(NUM_ROIS), kind=Kind.normal, lazy=True, **kwargs
):
    """Add one or more ROIs to an MCA instance

    Parameters
    ----------
    range_ : sequence of ints
        Must be be in the set [0,31]

    By default, an EpicsMCA is initialized with all 32 rois. These
    provide the following Components as EpicsSignals (N=[0,31]):
    EpicsMCA.rois.roiN.(label,count,net_count,preset_cnt, is_preset,
    bkgnd_chans, hi_chan, lo_chan)

    """
    defn = OrderedDict()
    kwargs["kind"] = kind
    kwargs["lazy"] = lazy
    for roi in range_:
        if not (0 <= roi <= 47):
            raise ValueError(f"roi {roi} must be in the set [0,47]")
        attr = f"roi{roi}"
        defn[attr] = (
            ROI,
            f"ROI:{roi+1}:",
            kwargs,
        )
    return defn


class MCARecord(MCASumMixin, Device):
    rois = DDC(add_rois(), kind=active_kind)
    spectrum = ADCpt(EpicsSignalRO, ":ArrayData", kind="normal", lazy=True)
    dead_time_percent = RECpt(
        EpicsSignalRO,
        ":DeadTime_RBV",
        pattern=r":MCA",
        repl=":C",
        lazy=True,
        kind="normal",
    )
    dead_time_factor = RECpt(
        EpicsSignalRO,
        ":DTFactor_RBV",
        pattern=r":MCA",
        repl=":C",
        lazy=True,
        kind="normal",
    )
    clock_ticks = RECpt(
        EpicsSignalRO,
        "SCA:0:Value_RBV",
        pattern=r":MCA",
        repl=":C",
        lazy=True,
        kind="normal",
    )
    _default_read_attrs = [
        "rois",
        "spectrum",
        "dead_time_percent",
        "dead_time_factor",
        "clock_ticks",
        "total_count",
    ]
    _default_configuration_attrs = ["rois"]
    kind = active_kind


def add_mcas(range_, kind=active_kind, **kwargs):
    """Add one or more MCARecords to a device

    Parameters
    ----------
    range_
      Indices for which to create MCA records.

    """
    defn = OrderedDict()
    kwargs["kind"] = kind
    kwargs["lazy"] = True
    for idx in range_:
        attr = f"mca{idx}"
        defn[attr] = (
            MCARecord,
            f"MCA{idx+1}",
            kwargs,
        )
    return defn


class Xspress3Detector(SingleTrigger_V34, DetectorBase, XRFMixin):
    """A fluorescence detector plugged into an Xspress3 readout."""

    _dead_times: dict

    def get_acquire_frames(self, mds: MultiDerivedSignal, items: SignalToValue) -> int:
        return items[self.acquire]

    def put_acquire_frames(
        self, mds: MultiDerivedSignal, value: OphydDataType, num_frames: int
    ) -> SignalToValue:
        return {
            self.cam.num_images: num_frames,
            self.acquire: value,
        }

    cam = ADCpt(CamMixin_V34, "det1:")
    # Core control interface signals
    detector_state = ADCpt(EpicsSignalRO, "det1:DetectorState_RBV", kind="omitted")
    acquire = ADCpt(SignalWithRBV, "det1:Acquire", kind="omitted")
    acquire_busy = ADCpt(EpicsSignalRO, "det1:AcquireBusy", kind="omitted")
    acquire_period = ADCpt(SignalWithRBV, "det1:AcquirePeriod", kind="omitted")
    dwell_time = ADCpt(SignalWithRBV, "det1:AcquireTime", kind="normal")
    erase = ADCpt(EpicsSignal, "det1:ERASE", kind="omitted")
    acquire_single = ADCpt(
        MultiDerivedSignal,
        attrs=["acquire", "cam.num_images"],
        calculate_on_get=get_acquire_frames,
        calculate_on_put=partial(put_acquire_frames, num_frames=1),
    )
    acquire_multiple = ADCpt(
        MultiDerivedSignal,
        attrs=["acquire", "cam.num_images"],
        calculate_on_get=get_acquire_frames,
        calculate_on_put=partial(put_acquire_frames, num_frames=2000),
    )
    # Dead time aggregate statistics
    dead_time_average = ADCpt(InternalSignal, kind="normal")
    dead_time_min = ADCpt(InternalSignal, kind="normal")
    dead_time_max = ADCpt(InternalSignal, kind="normal")

    # Number of elements is overridden by subclasses
    mcas = DDC(
        add_mcas(range_=range(1)),
        kind=active_kind,
        default_read_attrs=["mca0"],
        default_configuration_attrs=["mca0"],
    )
    roi_sums = DDC(
        add_roi_sums(mcas=range(1), rois=range(NUM_ROIS)),
        kind=active_kind,
        default_read_attrs=[f"roi{i}" for i in range(NUM_ROIS)],
        default_configuration_attrs=[f"roi{i}" for i in range(NUM_ROIS)],
    )

    _default_read_attrs = [
        "cam",
        "mcas",
        "roi_sums",
        "dead_time_average",
        "dead_time_min",
        "dead_time_max",
    ]
    _default_configuration_attrs = [
        "cam",
        "mcas",
    ]

    class erase_states(IntEnum):
        DONE = 0
        ERASE = 1

    class acquire_states(IntEnum):
        DONE = 0
        ACQUIRE = 1

    class detector_states(IntEnum):
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

    class trigger_modes(IntEnum):
        SOFTWARE = 0
        INTERNAL = 1
        IDC = 2
        TTL_VETO_ONLY = 3
        TTL_BOTH = 4
        LVDS_VETO_ONLY = 5
        LVDS_BOTH = 6

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stage_sigs[self.cam.trigger_mode] = self.trigger_modes.INTERNAL
        self.stage_sigs[self.cam.num_images] = 1
        # The image mode is not a real signal in the Xspress3 IOC
        del self.stage_sigs["cam.image_mode"]
        # Set up subscriptions for dead-time calculations
        self._dead_times = {}
        for mca in self.mca_records():
            mca.dead_time_percent.subscribe(self._update_dead_time_calcs)

    @property
    def default_time_signal(self):
        return self.cam.acquire_time

    def _update_dead_time_calcs(self, *args, value, obj, **kwargs):
        self._dead_times[obj.name] = value
        # Calculate aggregate dead time stats
        dead_times = np.asarray(list(self._dead_times.values()))
        self.dead_time_average.put(float(np.mean(dead_times)), internal=True)
        self.dead_time_min.put(float(np.min(dead_times)), internal=True)
        self.dead_time_max.put(float(np.max(dead_times)), internal=True)

    @property
    def stage_num_frames(self):
        """How many frames to prepare for when staging this detector."""
        return self.stage_sigs.get(self.num_frames, 1)

    @stage_num_frames.setter
    def stage_num_frames(self, val):
        self.stage_sigs[self.num_frames] = val

    @property
    def num_elements(self):
        return len(self.mcas.component_names)

    def save_fly_datum(self, *, value, timestamp, obj, **kwargs):
        """Callback to save data from a signal during fly-scanning."""
        datum = (timestamp, value)
        self._fly_data.setdefault(obj, []).append(datum)

    def fly_data(self):
        """Compile the fly-scan data into a pandas dataframe.

        Some stray rows show up at the beginning that get dropped:

        - Old image counter with previous values capturing when
          subscribing. Needed to make sure we have an entry for all
          the signals.
        - The counts collected during taxiing.

        """
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
        # Drop the extra rows that come from the subscription setup
        data = data.iloc[1:]
        timestamps = timestamps.iloc[1:]
        # Drop extra rows from before and during taxi
        for idx in [-2, -1]:
            try:
                data.drop(idx, inplace=True)
                timestamps.drop(idx, inplace=True)
            except KeyError:
                continue
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

    def kickoff(self) -> StatusBase:
        # Set up subscriptions for capturing data
        self._fly_data = {}
        for walk in self.walk_fly_signals():
            sig = walk.item
            sig.subscribe(self.save_fly_datum, run=True)

        # Set up the status for when the detector is ready to fly
        def check_acquiring(*, old_value, value, **kwargs):
            is_acquiring = value == self.detector_states.ACQUIRE
            if is_acquiring:
                self.start_fly_timestamp = time.time()
            return is_acquiring

        status = SubscriptionStatus(self.detector_state, check_acquiring)
        # Set the right parameters
        status &= self.cam.trigger_mode.set(self.trigger_modes.TTL_VETO_ONLY)
        status &= self.cam.num_images.set(2**14)
        status &= self.acquire.set(self.acquire_states.ACQUIRE)
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
        return self.acquire.set(0)

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
        for walk in self.walk_fly_signals():
            desc.update(walk.item.describe())
        return {self.name: desc}


def make_xspress_device(name, prefix, num_elements):
    # Build the mca components
    # (Epics uses 1-index instead of 0-index)
    mca_range = range(num_elements)
    attrs = {
        "mcas": DDC(
            add_mcas(range_=mca_range),
            kind=active_kind,
            default_read_attrs=[f"mca{i}" for i in mca_range],
            default_configuration_attrs=[f"mca{i}" for i in mca_range],
        ),
        "roi_sums": DDC(
            add_roi_sums(mcas=mca_range, rois=range(NUM_ROIS)),
            kind=active_kind,
            default_read_attrs=[f"roi{i}" for i in range(NUM_ROIS)],
            default_configuration_attrs=[f"roi{i}" for i in range(NUM_ROIS)],
        ),
    }
    # Create a dynamic subclass with the MCAs
    class_name = name.title().replace("_", "")
    parent_classes = (Xspress3Detector,)
    Cls = type(class_name, parent_classes, attrs)
    return make_device(
        Cls,
        name=name,
        prefix=f"{prefix}:",
        labels={"xrf_detectors", "fluorescence_detectors", "detectors"},
    )


def load_xspress_detectors(config=None):
    """Load all the xspress-based detector devices.

    Configuration is determined from the iconfig.toml file.

    Optionally, *config* can be given a dictionary with configuration
    matching the iconfig.toml file to use instead. Mostly useful for
    testing.

    """
    if config is None:
        config = load_config()
    # Create detector device
    devices = []
    for name, cfg in config.get("xspress", {}).items():
        devices.append(
            make_xspress_device(
                prefix=cfg["prefix"], num_elements=cfg["num_elements"], name=name
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
