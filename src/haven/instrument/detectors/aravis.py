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
    AravisController,
)
from ophyd_async.core import YMDPathProvider, UUIDFilenameProvider, SubsetEnum
from ophyd_async.epics.signal import epics_signal_rw_rbv, epics_signal_r
from ophyd_async.epics.adcore import (
    NDFileHDFIO,
    ADHDFWriter,
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


class AravisDriverIO(AravisDriverIOBase):
    def __init__(self, prefix: str, name: str = "") -> None:
        super().__init__(prefix, name=name)
        self.trigger_source = epics_signal_rw_rbv(
            AravisTriggerSource, prefix + "TriggerSource"
        )


class AravisDetector(AravisDetectorBase):
    def __init__(
        self,
        prefix: str,
        path_provider=None,
        drv_suffix="cam1:",
        hdf_suffix="HDF1:",
        name="",
        gpio_number: AravisController.GPIO_NUMBER = 1,
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
