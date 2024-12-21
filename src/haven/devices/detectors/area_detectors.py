from pathlib import Path

from ophyd_async.core import (
    DeviceVector,
    PathProvider,
    SubsetEnum,
    UUIDFilenameProvider,
    YMDPathProvider,
)
from ophyd_async.epics.adcore._core_io import NDPluginBaseIO
from ophyd_async.epics.core import epics_signal_rw_rbv

from ..._iconfig import load_config


class OverlayShape(SubsetEnum):
    CROSS = "Cross"
    RECTANGLE = "Rectangle"
    ELLIPSE = "Ellipse"
    TEXT = "Text"


class OverlayPlugin(NDPluginBaseIO):
    def __init__(self, prefix: str, name: str = "") -> None:
        self.shape = epics_signal_rw_rbv(OverlayShape, f"{prefix}Shape")
        self.center_x = epics_signal_rw_rbv(int, f"{prefix}CenterX")
        self.center_y = epics_signal_rw_rbv(int, f"{prefix}CenterY")
        self.size_x = epics_signal_rw_rbv(int, f"{prefix}SizeX")
        self.size_y = epics_signal_rw_rbv(int, f"{prefix}SizeY")
        super().__init__(prefix=prefix, name=name)


class HavenDetector:
    def __init__(
        self, *args, prefix: str, path_provider: PathProvider | None = None, **kwargs
    ):
        # Add additional non-data plugins
        self.overlays = DeviceVector(
            {idx: OverlayPlugin(f"{prefix}Over1:{idx+1}:") for idx in range(8)}
        )
        # Determine a default path provider to use
        if path_provider is None:
            path_provider = default_path_provider()
        super().__init__(*args, prefix=prefix, path_provider=path_provider, **kwargs)


def default_path_provider(path: Path = None, config=None):
    if config is None:
        config = load_config()
    if path is None:
        path = Path(config.get("area_detector_root_path", "/tmp"))
    path_provider = YMDPathProvider(
        filename_provider=UUIDFilenameProvider(),
        base_directory_path=path,
        create_dir_depth=-4,
    )
    return path_provider
