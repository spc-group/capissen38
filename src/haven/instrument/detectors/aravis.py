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
    AravisDriverIO,
    AravisController,
)
from ophyd_async.core import YMDPathProvider, UUIDFilenameProvider, SubsetEnum, DeviceVector, StandardReadable, Device, HintedSignal, ConfigSignal
from ophyd_async.epics.signal import epics_signal_rw_rbv, epics_signal_r
from ophyd_async.epics.adcore import (
    NDFileHDFIO,
    ADHDFWriter,
    NDPluginStatsIO,
    ADBaseShapeProvider,
    ADBaseDataType,
)

from ... import exceptions
from ..._iconfig import load_config
from ..area_detector import (  # noqa: F401
    AsyncCamMixin,
    DetectorBase,
    SimDetector,
    SingleImageModeTrigger,
    StatsPlugin_V34,
)
from ..device import make_device, connect_devices
from ..instrument_registry import InstrumentRegistry
from ..instrument_registry import registry as default_registry

log = logging.getLogger(__name__)


__all__ = ["AravisDetector", "load_cameras"]


AravisTriggerSource = SubsetEnum["Software", "Line1"]


class StatsPlugin(StandardReadable, NDPluginStatsIO):
    async def connect(self, *args, **kwargs):
        await super().connect(*args, **kwargs)
    
    def __init__(self, prefix, name=""):
        # Hinted signals
        with self.add_children_as_readables(HintedSignal):
            self.max = epics_signal_r(int, f"{prefix}MaxValue_RBV")
            self.total = epics_signal_r(int, f"{prefix}Total_RBV")
            self.mean = epics_signal_r(int, f"{prefix}MeanValue_RBV")
            self.net = epics_signal_r(int, f"{prefix}Net_RBV")
        # Readable signals
        with self.add_children_as_readables():
            self.min = epics_signal_r(int, f"{prefix}MinValue_RBV")
            self.min_x = epics_signal_r(int, f"{prefix}MinX_RBV")
            self.min_y = epics_signal_r(int, f"{prefix}MinY_RBV")
            self.max_x = epics_signal_r(int, f"{prefix}MaxX_RBV")
            self.max_y = epics_signal_r(int, f"{prefix}MaxY_RBV")
            self.sigma = epics_signal_r(int, f"{prefix}Sigma_RBV")
        # Configuration signals
        with self.add_children_as_readables(ConfigSignal):
            self.data_type = epics_signal_r(ADBaseDataType, f"{prefix}DataType_RBV")
            self.color_mode = epics_signal_r(str, f"{prefix}ColorMode_RBV")
        super().__init__(prefix=prefix, name=name)


class AravisDetector(StandardReadable):
    """A camera operated through an Aravis area detector IOC."""
    def __init__(self, prefix: str, name: str = "", stats_count=4):
        with self.add_children_as_readables():
            # Fly-scannable detection system
            self.det = AravisDetectionSystem(prefix=prefix, name="det")
            # ND plugins for calculating stats
            self.stats = DeviceVector(
                {i: StatsPlugin(f"{prefix}Stats{i+1}:") for i in range(stats_count)}
            )
        # Make the detection system controls easier to get to
        self.drv = self.det.drv
        self.hdf = self.det.hdf
        super().__init__(name=name)

class AravisDetectionSystem(AravisDetectorBase):
    def __init__(
        self,
        prefix: str,
        path_provider=None,
        drv_suffix="cam1:",
        hdf_suffix="HDF1:",
        name="",
        gpio_number: AravisController.GPIO_NUMBER = 1,
        status_count: int = 4,
    ):
        """Inialize a detector for Aravis-based camera.

        Parameters
        ==========
        prefix
          The IOC prefix (e.g. "25idcgigeB:")
        name
          The device name for this hardware.
        path_provider
          A PathProvider object for setting up file storage. If
          omitted, a default %Y/%m/%d structure will be used.

        """
        # Generate a default path provider
        if path_provider is None:
            config = load_config()
            root_dir = config["area_detector"].get("root_path", "/tmp")
            path_provider = YMDPathProvider(
                filename_provider=UUIDFilenameProvider(),
                directory_path=root_dir,
            )
        # Prepare sub-components
        self.drv = AravisDriverIO(f"{prefix}{drv_suffix}")
        self.drv.trigger_source = epics_signal_rw_rbv(
            AravisTriggerSource, f"{prefix}{drv_suffix}TriggerSource"
        )
        self.hdf = NDFileHDFIO(f"{prefix}{hdf_suffix}")
        super(AravisDetectorBase, self).__init__(
            AravisController(self.drv, gpio_number=gpio_number),
            ADHDFWriter(
                self.hdf,
                path_provider,
                lambda: self.name,
                ADBaseShapeProvider(self.drv),
            ),
            config_sigs=(self.drv.acquire_time,),
            name=name,
        )

        # Fix signals that don't match our AD
        self.drv.data_type = epics_signal_r(
            ADBaseDataType,
            f"{prefix}{drv_suffix}DataType_RBV",
            name=self.drv.data_type.name,
        )
        self.hdf.data_type = epics_signal_r(
            ADBaseDataType,
            f"{prefix}{hdf_suffix}DataType_RBV",
            name=self.hdf.data_type.name,
        )


# -----------------------------------------------------------------------------
# :author:    Mark Wolfman
# :email:     wolfman@anl.gov
# :copyright: Copyright © 2024, UChicago Argonne, LLC
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
