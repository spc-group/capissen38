from ophyd_async.core import PathProvider, SubsetEnum
from ophyd_async.epics.adaravis import AravisDetector as DetectorBase
from ophyd_async.epics.core import epics_signal_rw_rbv

from .area_detectors import HavenDetector, default_path_provider


class AravisTriggerSource(SubsetEnum):
    SOFTWARE = "Software"
    LINE1 = "Line1"


class AravisDetector(HavenDetector, DetectorBase):
    _ophyd_labels_ = {"cameras", "detectors"}

    def __init__(
        self, prefix, *args, path_provider: PathProvider | None = None, **kwargs
    ):
        if path_provider is None:
            path_provider = default_path_provider()
        super().__init__(*args, prefix=prefix, path_provider=path_provider, **kwargs)
        # Replace a signal that has different enum options
        self.drv.trigger_source = epics_signal_rw_rbv(
            AravisTriggerSource,  # type: ignore
            f"{prefix}cam1:TriggerSource",
        )
        self.set_name(self.name)
