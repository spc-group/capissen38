from ophyd_async.epics.adsimdetector import SimDetector as SimDetectorBase

from haven._iconfig import load_config

from .area_detectors import HavenDetector


class SimDetector(HavenDetector, SimDetectorBase):
    _ophyd_labels_ = {"area_detectors", "detectors"}

    def __init__(self, prefix, path_provider=None, **kwargs):
        path_provider = path_provider or load_config().get(
            "area_detector_root_path", "/default/path"
        )
        super().__init__(prefix=prefix, path_provider=path_provider, **kwargs)
