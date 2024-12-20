import time
from collections import namedtuple
from enum import IntEnum

import pandas as pd
import numpy as np
from ophyd.flyers import FlyerInterface
from ophyd import Device, Signal, Component as Cpt, Kind
from ophyd.status import StatusBase, SubscriptionStatus, Status


fly_event = namedtuple("fly_event", ("timestamp", "value"))


class AcquireState(IntEnum):
    DONE = 0
    ACQUIRE = 1


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


class ImageMode(IntEnum):
    SINGLE = 0
    MULTIPLE = 1
    CONTINUOUS = 2


class TriggerMode(IntEnum):
    SOFTWARE = 0
    INTERNAL = 1
    IDC = 2
    TTL_VETO_ONLY = 3
    TTL_BOTH = 4
    LVDS_VETO_ONLY = 5
    LVDS_BOTH = 6


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

    def describe_collect(self) -> dict[str, dict]:
        """Describe details for the flyer collect() method"""
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
