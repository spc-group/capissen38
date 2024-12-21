import warnings
from typing import Mapping

import numpy as np
from ophyd import Device
from ophyd.areadetector.filestore_mixins import FileStoreHDF5IterativeWrite
from ophyd.areadetector.plugins import HDF5Plugin_V34

from ..._iconfig import load_config


class DynamicFileStore(Device):
    """File store mixin that alters the write_path_template based on
    iconfig values.

    """

    def __init__(
        self, *args, write_path_template="/{root_path}/{name}/%Y/%m/", **kwargs
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
