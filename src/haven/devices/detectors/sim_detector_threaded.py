from apstools.devices import CamMixin_V34, SingleTrigger_V34
from ophyd import ADComponent as ADCpt, SimDetectorCam
from ophyd.areadetector.plugins import (
    ImagePlugin_V34,
    OverlayPlugin_V34,
    PvaPlugin_V34,
)

from .area_detectors_threaded import DetectorBase
from .hdf_threaded import HDF5FilePlugin


class SimDetectorCam_V34(CamMixin_V34, SimDetectorCam): ...


class SimDetectorThreaded(SingleTrigger_V34, DetectorBase):
    """
    ADSimDetector
    SingleTrigger:
    * stop any current acquisition
    * sets image_mode to 'Multiple'
    """

    cam = ADCpt(SimDetectorCam_V34, "cam1:")
    pva = ADCpt(PvaPlugin_V34, "Pva1:", kind="omitted")
    hdf = ADCpt(
        HDF5FilePlugin,
        "HDF1:",
        write_path_template="/tmp/",
    )


