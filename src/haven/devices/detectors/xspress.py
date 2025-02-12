import asyncio
import xml.etree.ElementTree as ET
from collections.abc import Sequence

import numpy as np
from ophyd_async.core import (
    Array1D,
    AsyncStatus,
    DetectorController,
    Device,
    DeviceVector,
    PathProvider,
    SignalR,
    StrictEnum,
    TriggerInfo,
    soft_signal_r_and_setter,
)
from ophyd_async.epics import adcore
from ophyd_async.epics.adcore import ADBaseController, AreaDetector
from ophyd_async.epics.adcore._utils import (
    ADBaseDataType,
    NDAttributeDataType,
    NDAttributeParam,
    convert_ad_dtype_to_np,
)
from ophyd_async.epics.core import epics_signal_r, epics_signal_rw, epics_signal_x

from .area_detectors import HavenDetector, default_path_provider


class XspressTriggerMode(StrictEnum):
    SOFTWARE = "Software"
    INTERNAL = "Internal"
    IDC = "IDC"
    TTL_VETO_ONLY = "TTL Veto Only"
    TTL_BOTH = "TTL Both"
    LVDS_VETO_ONLY = "LVDS Veto Only"
    LVDS_BOTH = "LVDS Both"
    SOFTWARE_INTERNAL = "Software + Internal"


class XspressDriverIO(adcore.ADBaseIO):
    def __init__(self, prefix, name=""):
        self.trigger_mode = epics_signal_rw(XspressTriggerMode, f"{prefix}TriggerMode")
        self.erase_on_start = epics_signal_rw(bool, f"{prefix}EraseOnStart")
        self.erase = epics_signal_x(f"{prefix}ERASE")
        self.deadtime_correction = epics_signal_rw(bool, f"{prefix}CTRL_DTC")
        self.number_of_elements = epics_signal_r(int, f"{prefix}MaxSizeY_RBV")
        super().__init__(prefix=prefix, name=name)


class XspressController(ADBaseController):
    def __init__(self, driver: adcore.ADBaseIO) -> None:
        super().__init__(driver)
        self.driver = driver

    def get_deadtime(self, exposure: float) -> float:
        # Arbitrary value. To-do: fill this in when we know what to
        # include
        return 0.001

    async def setup_ndattributes(self, device_name: str):
        num_elements = await self.driver.number_of_elements.get_value()
        params = ndattribute_params(
            device_name=device_name, elements=range(num_elements)
        )
        xml = ndattribute_xml(params)
        await self.driver.nd_attributes_file.set(xml)

    @AsyncStatus.wrap
    async def prepare(self, trigger_info: TriggerInfo):
        await asyncio.gather(
            self.driver.num_images.set(trigger_info.total_number_of_triggers),
            self.driver.image_mode.set(adcore.ImageMode.MULTIPLE),
            self.driver.trigger_mode.set(XspressTriggerMode.INTERNAL),
            # Hardware deadtime correciton is not reliable
            # https://github.com/epics-modules/xspress3/issues/57
            self.driver.deadtime_correction.set(False),
        )


class XspressDatasetDescriber(adcore.ADBaseDatasetDescriber):
    """The datatype cannot be reliably determined from DataType_RBV.

    Instead, read out whether deadtime correction is enabled and
    determine the datatype this way.

    https://github.com/epics-modules/xspress3/issues/57

    """

    async def np_datatype(self) -> str:
        dt_correction = await self._driver.deadtime_correction.get_value()
        if dt_correction:
            return convert_ad_dtype_to_np(ADBaseDataType.FLOAT64)
        else:
            return convert_ad_dtype_to_np(ADBaseDataType.UINT32)


class XspressElement(Device):
    """Data and controls for an individual Xspress3 detector element."""

    def __init__(self, prefix: str, element_index: int, name: str = ""):
        """Parameters
        ==========
        prefix
          The detector's overall PV prefix, not including the
          e.g. "MCA1:" part.
        element_index
          This elements positional index, e.g. the first element will
          have *element_index*=0.

        """
        elem_num = element_index + 1
        self.spectrum = epics_signal_r(
            Array1D[np.float64], f"{prefix}MCA{elem_num}:ArrayData"
        )
        self.dead_time_percent = epics_signal_r(
            float, f"{prefix}C{elem_num}SCA:10:Value_RBV"
        )
        self.dead_time_factor = epics_signal_r(
            float, f"{prefix}C{elem_num}SCA:9:Value_RBV"
        )
        super().__init__(name=name)


class Xspress3Detector(HavenDetector, AreaDetector):
    """A detector controlled by Xspress3 electronics.

    The elements of the detector are represented on the *mcas*
    attribute. The number of mcas is determined by passing *elements*
    when initializing an object. *elements* can be either an integer,
    in which case it represents to number of elements, or an iterator
    representing the index of each element.

    The following lines are equivalent.

    .. code-block:: python

      det = Xspress3Detector(..., elements=4)

      det = Xspress3Detector(..., elements=[0, 1, 2, 3])

      det = Xspress3Detector(..., elements=range(4))

    The parameter *ev_per_bin* controls the conversion from histogram
    bin to energy. This is set during calibration; changing the value
    passed into this class without re-calibrating the detector **will
    result in an incorrect conversion**.

    """

    _ophyd_labels_ = {"detectors", "xrf_detectors"}
    _controller: DetectorController
    _writer: adcore.ADHDFWriter

    def __init__(
        self,
        prefix: str,
        path_provider: PathProvider | None = None,
        elements: int | Sequence[int] = 1,
        ev_per_bin: float = 10.0,
        drv_suffix="det1:",
        fileio_suffix="HDF1:",
        name: str = "",
        config_sigs: Sequence[SignalR] = (),
    ):
        # Per-element MCA devices
        try:
            elements = range(elements)
        except TypeError:
            pass
        self.elements = DeviceVector(
            {idx: XspressElement(prefix, element_index=idx) for idx in elements}
        )
        # Area detector IO devices
        self.driver = XspressDriverIO(prefix + drv_suffix)
        self.fileio = adcore.NDFileHDFIO(prefix + fileio_suffix)

        self.plugins = {"hdf": self.fileio}

        if path_provider is None:
            path_provider = default_path_provider()
        # Extra configuration signals
        self.ev_per_bin, _ = soft_signal_r_and_setter(float, initial_value=ev_per_bin)

        super().__init__(
            controller=XspressController(self.driver),
            writer=adcore.ADHDFWriter(
                fileio=self.fileio,
                path_provider=path_provider,
                name_provider=lambda: self.name,
                dataset_describer=XspressDatasetDescriber(self.driver),
                # driver=self.driver,  # <- for DT ndattributes
                plugins=self.plugins,
            ),
            plugins=self.plugins,
            config_sigs=(
                self.driver.acquire_period,
                self.driver.acquire_time,
                self.ev_per_bin,
                *config_sigs,
            ),
            name=name,
        )

    @AsyncStatus.wrap
    async def stage(self) -> None:
        self._old_xml_file, *_ = await asyncio.gather(
            self.driver.nd_attributes_file.get_value(),
            super().stage(),
            self._controller.setup_ndattributes(device_name=self.name),
            self.driver.erase_on_start.set(False),
            self.driver.erase.trigger(),
        )

    @AsyncStatus.wrap
    async def unstage(self) -> None:
        await super().unstage()
        if self._old_xml_file is not None:
            # Restore the original XML attributes file
            await self.driver.nd_attributes_file.set(self._old_xml_file)
            self._old_xml_file = None

    @property
    def default_time_signal(self):
        return self.driver.acquire_time


def ndattribute_xml(params):
    """Convert a set of NDAttribute params to XML."""
    root = ET.Element("Attributes")
    for ndattribute in params:
        ET.SubElement(
            root,
            "Attribute",
            name=ndattribute.name,
            type="PARAM",
            source=ndattribute.param,
            addr=str(ndattribute.addr),
            datatype=ndattribute.datatype.value,
            description=ndattribute.description,
        )
    xml_text = ET.tostring(root, encoding="unicode")
    return xml_text


def ndattribute_params(
    device_name: str, elements: Sequence[int]
) -> Sequence[NDAttributeParam]:
    """Create a set of ndattribute params that can be written to the AD's
    HDF5 file.

    These parameters can then be used with something like
    :py:func:`ophyd_async.plan_stubs.setup_ndattributes` to build the
    XML.

    """
    params = []
    for idx in elements:
        new_params = [
            NDAttributeParam(
                name=f"{device_name}-element{idx}-deadtime_factor",
                param="XSP3_CHAN_DTFACTOR",
                datatype=NDAttributeDataType.DOUBLE,
                addr=idx,
                description=f"Chan {idx} DTC Factor",
            ),
            # The following attributes are not required, and so are removed for efficiency
            #   but can be re-enabled for testing.
            #
            # NDAttributeParam(
            #     name=f"{device_name}-element{idx}-deadtime_percent",
            #     param="XSP3_CHAN_DTPERCENT",
            #     datatype=NDAttributeDataType.DOUBLE,
            #     addr=idx,
            #     description=f"Chan {idx} DTC Percent",
            # ),
            # NDAttributeParam(
            #     name=f"{device_name}-element{idx}-event_width",
            #     param="XSP3_EVENT_WIDTH",
            #     datatype=NDAttributeDataType.DOUBLE,
            #     addr=idx,
            #     description=f"Chan {idx} Event Width",
            # ),
            # NDAttributeParam(
            #     name=f"{device_name}-element{idx}-clock_ticks",
            #     param="XSP3_CHAN_SCA0",
            #     datatype=NDAttributeDataType.DOUBLE,
            #     addr=idx,
            #     description=f"Chan {idx} ClockTicks",
            # ),
            # NDAttributeParam(
            #     name=f"{device_name}-element{idx}-reset_ticks",
            #     param="XSP3_CHAN_SCA1",
            #     datatype=NDAttributeDataType.DOUBLE,
            #     addr=idx,
            #     description=f"Chan {idx} ResetTicks",
            # ),
            # NDAttributeParam(
            #     name=f"{device_name}-element{idx}-reset_counts",
            #     param="XSP3_CHAN_SCA2",
            #     datatype=NDAttributeDataType.DOUBLE,
            #     addr=idx,
            #     description=f"Chan {idx} ResetCounts",
            # ),
            # NDAttributeParam(
            #     name=f"{device_name}-element{idx}-all_event",
            #     param="XSP3_CHAN_SCA3",
            #     datatype=NDAttributeDataType.DOUBLE,
            #     addr=idx,
            #     description=f"Chan {idx} AllEvent",
            # ),
            # NDAttributeParam(
            #     name=f"{device_name}-element{idx}-all_good",
            #     param="XSP3_CHAN_SCA4",
            #     datatype=NDAttributeDataType.DOUBLE,
            #     addr=idx,
            #     description=f"Chan {idx} AllGood",
            # ),
            # NDAttributeParam(
            #     name=f"{device_name}-element{idx}-pileup",
            #     param="XSP3_CHAN_SCA7",
            #     datatype=NDAttributeDataType.DOUBLE,
            #     addr=idx,
            #     description=f"Chan {idx} Pileup",
            # ),
        ]
        params.extend(new_params)
    return params
