import time
import warnings
from collections import OrderedDict
from enum import IntEnum
from typing import Optional, Sequence

from ophyd import Component as Cpt
from ophyd import DynamicDeviceComponent as DDC
from ophyd import Kind, Signal, flyers, mca
from ophyd.signal import DerivedSignal, InternalSignal
from ophyd.status import StatusBase, SubscriptionStatus

from .. import exceptions
from .._iconfig import load_config
from .device import make_device
from .fluorescence_detector import (
    MCASumMixin,
    ROIMixin,
    UseROISignal,
    XRFMixin,
    active_kind,
    add_roi_sums,
)

__all__ = ["DxpDetector", "load_dxp_detectors"]


NUM_ROIS = 32


class SizeSignal(DerivedSignal):
    def inverse(self, hi):
        lo = self.parent.lo_chan.get()
        size = hi - lo
        return size

    def forward(self, size):
        lo = self.parent.lo_chan.get()
        hi = lo + size
        return hi


class ROI(ROIMixin, mca.ROI):
    _default_read_attrs = [
        "count",
        "net_count",
    ]
    _default_configuration_attrs = [
        "label",
        "bkgnd_chans",
        "hi_chan",
        "lo_chan",
    ]
    kind = active_kind
    # Signals
    use = Cpt(UseROISignal, derived_from="label", kind="config")
    size = Cpt(SizeSignal, derived_from="hi_chan", kind="config")

    def unstage(self):
        # Restore original signal kinds
        for fld, kind in self._original_kinds.items():
            getattr(self, fld).kind = kind
        super().unstage()


def add_rois(range_: Sequence[int] = range(NUM_ROIS), kind=Kind.normal, **kwargs):
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
    for roi in range_:
        if not (0 <= roi < 32):
            raise ValueError("roi must be in the set [0,31]")
        attr = "roi{}".format(roi)
        defn[attr] = (
            ROI,
            ".R{}".format(roi),
            kwargs,
        )
    return defn


class MCARecord(MCASumMixin, mca.EpicsMCARecord):
    rois = DDC(add_rois(), kind=active_kind)
    dead_time_factor = Cpt(Signal, kind=Kind.normal)
    dead_time_percent = Cpt(Signal, kind=Kind.normal)
    _default_read_attrs = [
        "rois",
        "total_count",
        "spectrum",
        "dead_time_factor",
        "dead_time_percent",
        # "preset_real_time",
        # "preset_live_time",
        # "elapsed_real_time",
        # "elapsed_live_time",
        # "background",
    ]
    _default_configuration_attrs = ["rois", "mode"]
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
    for idx in range_:
        attr = f"mca{idx}"
        defn[attr] = (
            MCARecord,
            f"mca{idx+1}",  # (Epics uses 1-index instead of 0-index)
            kwargs,
        )
    return defn


class DxpDetector(
    XRFMixin,
    flyers.FlyerInterface,
    mca.EpicsDXPMapping,
    mca.EpicsDXPMultiElementSystem,
):
    """A fluorescence detector based on XIA-DXP XMAP electronics.

    Creates MCA components based on the number of elements.

    """

    class CollectMode(IntEnum):
        MCA_SPECTRA = 0
        MCA_MAPPING = 1
        SCA_MAPPING = 2
        LIST_MAPPING = 3

    write_path: str = "M:\\epics\\fly_scanning\\"
    read_path: str = "/net/s20data/sector20/tmp/"
    acquire = Cpt(Signal, value=0)

    # Dead time aggregate statistics
    dead_time_average = Cpt(InternalSignal, kind="normal")
    dead_time_min = Cpt(InternalSignal, kind="normal")
    dead_time_max = Cpt(InternalSignal, kind="normal")

    # By default, a 4-element detector, subclass for more elements
    mcas = DDC(
        add_mcas(range_=range(4)),
        default_read_attrs=["mca0", "mca1", "mca2", "mca3"],
        default_configuration_attrs=["mca0", "mca1", "mca2", "mca3"],
    )
    roi_sums = DDC(
        add_roi_sums(mcas=range(1), rois=range(NUM_ROIS)),
        kind=active_kind,
        default_read_attrs=[f"roi{i}" for i in range(NUM_ROIS)],
        default_configuration_attrs=[f"roi{i}" for i in range(NUM_ROIS)],
    )

    # net_cdf = Cpt(NetCDFPlugin_V34, "netCDF1:")
    _default_read_attrs = [
        # "preset_live_time",
        # "preset_real_time",
        # "dead_time",
        # "elapsed_live",
        # "elapsed_real",
        "roi_sums",
        "mcas",
        "dead_time_average",
        "dead_time_max",
        "dead_time_min",
    ]
    _default_configuration_attrs = [
        "max_scas",
        "num_scas",
        "poll_time",
        "prescale",
        "preset_mode",
        "preset_events",
        "preset_triggers",
        "snl_connected",
        "mcas",
    ]
    _omitted_attrs = [  # Just save them here for easy reference
        "channel_advance",
        "client_wait",
        "dwell",
        "save_system",
        "save_system_file",
        "set_client_wait",
        "erase_all",
        "erase_start",
        "start_all",
        "stop_all",
        "set_acquire_busy",
        "acquire_busy",
        "status_all",
        "status_all_once",
        "acquiring",
        "read_baseline_histograms",
        "read_all",
        "read_all_once",
        "copy_adcp_ercent_rule",
        "copy_baseline_cut_enable",
        "copy_baseline_cut_percent",
        "copy_baseline_filter_length",
        "copy_baseline_threshold",
        "copy_decay_time",
        "copy_detector_polarity",
        "copy_energy_threshold",
        "copy_gap_time",
        "copy_max_energy",
        "copy_max_width",
        "copy_peaking_time",
        "copy_preamp_gain",
        "copy_roic_hannel",
        "copy_roie_nergy",
        "copy_roi_sca",
        "copy_reset_delay",
        "copy_trigger_gap_time",
        "copy_trigger_peaking_time",
        "copy_trigger_threshold",
        "do_read_all",
        "do_read_baseline_histograms",
        "do_read_traces",
        "do_status_all",
        "read_low_level_params",
        "read_traces",
        "trace_modes",
        "trace_times",
        "idead_time",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stage_sigs[self.collect_mode] = self.CollectMode.MCA_SPECTRA
        # Listen for changes to the ``acquire`` channel.
        self.acquire.subscribe(self._acquire)
        self.acquiring.subscribe(self._acquire)

    @property
    def default_time_signal(self):
        return self.preset_real_time

    def _acquire(self, *args, old_value, value, obj, **kwargs):
        """Mimic the Xspress3 AD interface for acquiring data."""
        if obj is self.acquire:
            # Update the real signals
            if bool(value):
                # Start
                self.erase_start.set(1).wait()
            else:
                # Stop
                self.stop_all.set(1).wait()
        elif obj is self.acquiring:
            # Update the virtual signal
            self.acquire.set(value).wait()

    def rois(self, roi_indices: Optional[Sequence[int]] = None):
        # Get the list of ROIs to activate
        all_rois = []
        for mca in self.mca_records():
            rois = mca.rois.component_names
            rois = [getattr(mca.rois, r) for r in rois]
            # Get sub-list if requested
            if roi_indices is not None:
                rois = [rois[i] for i in roi_indices]
            all_rois.extend(rois)
        return all_rois

    def kickoff(self) -> StatusBase:
        """Start the detector flying.

        This starts acquisition, starts the file writer, and sets the
        detector to advance to the next when it receives a gate
        signal. The returned status object will be complete when the
        detector reports that it is acquiring.

        Returns
        =======
        StatusBase
          Becomes complete once the detector is acquiring and ready to
          measure data.

        """
        # Make sure the CDF file write plugin is primed (assumes
        # dimensions will be empty when not primed)
        is_primed = len(self.net_cdf.dimensions.get()) > 0
        if not is_primed:
            msg = f"{self.net_cdf.name} plugin not primed."
            warnings.warn(msg, RuntimeWarning)
            exc = exceptions.PluginNotPrimed(msg)
            status = StatusBase()
            status.set_exception(exc)
            return status

        # Set up the status for when the detector is ready to fly
        def check_acquiring(*, old_value, value, **kwargs):
            is_acquiring = bool(value)
            if is_acquiring:
                self.start_timestamp = time.time()
            return is_acquiring

        status = SubscriptionStatus(self.acquiring, check_acquiring)
        # Configure the mapping controls
        self.collect_mode.set(self.CollectMode.MCA_MAPPING)
        self.pixel_advance_mode.set("Gate")
        # Configure the netCDF file writer
        self.net_cdf.enable.set("Enable").wait()
        [
            status.wait()
            for status in [
                self.net_cdf.file_path.set(self.write_path),
                self.net_cdf.file_name.set("fly_scan_temp.nc"),
                self.net_cdf.file_write_mode.set("Capture"),
            ]
        ]
        self.net_cdf.capture.set(1).wait()
        # Start the detector
        self.erase_start.set(1)
        return status

    def complete(self) -> StatusBase:
        """Wait for the detector to finish flying.

        This will stop the file writers and acquisition then return a
        status object. The status object will report complete once the
        detector acquire status reports that the detector is not
        acquiring.

        Returns
        =======
        StatusBase
          Becomes complete once the detector has finished acquiring
          and is ready to report the collected data.

        """
        # Stop the CDF file writer
        self.net_cdf.capture.set(0).wait()
        self.stop_all.set(1)

        # Set up the status for when the detector is done collecting
        def check_acquiring(*, old_value, value, **kwargs):
            is_acquiring = bool(value)
            return not is_acquiring

        status = SubscriptionStatus(self.acquiring, check_acquiring)
        return status


def parse_xmap_buffer(buff):
    """Extract meaningful data from an XMAP internal buffer during mapping.

    For more information, see section 5.3.3 of
    https://cars9.uchicago.edu/software/epics/XMAP_User_Manual.pdf

    """
    data = {"header": {}}
    header = buff[:256]
    # Verify tag words
    assert header[0] == 0x55AA
    assert header[1] == 0xAA55
    # Parse remaining buffer header
    head_data = data["header"]
    head_data["buffer_header_size"] = header[2]
    head_data["mapping_mode"] = header[3]
    head_data["run_number"] = header[4]
    head_data["buffer_number"] = header[5:7]
    head_data["buffer_id"] = header[7]
    head_data["num_pixels"] = header[8]
    head_data["starting_pixel"] = header[9:11]
    head_data["module"] = header[11]
    head_data["buffer_overrun"] = header[24]
    # head_data[""] =
    return data


def make_dxp_device(device_name, prefix, num_elements):
    # Build the mca components
    mca_range = range(0, num_elements)
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
    class_name = device_name.title().replace("_", "")
    parent_classes = (DxpDetector,)
    Cls = type(class_name, parent_classes, attrs)
    return make_device(
        Cls,
        prefix=f"{prefix}:",
        name=device_name,
        labels={"xrf_detectors", "fluorescence_detectors", "detectors"},
    )


def load_dxp_detectors(config=None):
    """Load all the DXP-based detector devices.

    Configuration is determined from the iconfig.toml file.

    Optionally, *config* can be given a dictionary with configuration
    matching the iconfig.toml file to use instead. Mostly useful for
    testing.

    """
    # Get the detector definitions from config files
    if config is None:
        config = load_config()
    devices = []
    for name, cfg in config.get("dxp", {}).items():
        devices.append(
            make_dxp_device(
                device_name=name,
                prefix=cfg["prefix"],
                num_elements=cfg["num_elements"],
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
