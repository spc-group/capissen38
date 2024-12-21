"""Loader for creating instances of the devices from a config file."""

import logging
import os
from typing import Mapping

from guarneri import Instrument

from .devices.aerotech import AerotechStage
from .devices.aps import ApsMachine
from .devices.area_detector import make_area_detector
from .devices.beamline_manager import BeamlineManager
from .devices.detectors.aravis import AravisDetector
from .devices.detectors.sim_detector import SimDetector
from .devices.detectors.xspress import Xspress3Detector
from .devices.dxp import make_dxp_device
from .devices.energy_positioner import EnergyPositioner
from .devices.heater import CapillaryHeater
from .devices.ion_chamber import IonChamber
from .devices.mirrors import HighHeatLoadMirror, KBMirrors
from .devices.motor import Motor, load_motors
from .devices.power_supply import NHQ203MChannel
from .devices.robot import Robot
from .devices.scaler import MultiChannelScaler
from .devices.shutter import PssShutter
from .devices.slits import ApertureSlits, BladeSlits
from .devices.stage import XYStage
from .devices.table import Table
from .devices.xia_pfcu import PFCUFilterBank

log = logging.getLogger(__name__)


class HavenInstrument(Instrument):
    def load(
        self,
        config: Mapping = None,
        return_devices: bool = False,
        reset_devices: bool = True,
    ):
        """Load the beamline instrumentation.

        This function will reach out and query various IOCs for motor
        information based on the information in *config* (see
        ``iconfig_default.toml`` for examples). Based on the
        configuration, it will create Ophyd devices and register them with
        *registry*.

        Parameters
        ==========
        config:
          The beamline configuration read in from TOML files. Mostly
          useful for testing.
        return_devices
          If true, return the newly loaded devices when complete.
        reset_registry
          If true, existing devices will be removed before loading.

        """
        if reset_devices:
            self.devices.clear()
        # Check if config files are available
        if "HAVEN_CONFIG_FILES" in os.environ:
            config_files = os.environ.get("HAVEN_CONFIG_FILES", "").split(":")
        else:
            config_files = []
        # Load devices ("motors" is done later)
        for cfg_file in config_files:
            super().load(cfg_file, return_exceptions=True, ignored_classes=["motors"])
        # VME-style Motors happen later so duplicate motors can be
        # removed
        for cfg_file in config_files:
            super().load(
                cfg_file,
                device_classes={"motors": load_motors},
                ignored_classes=self.device_classes.keys(),
            )
        # Return the final list
        if return_devices:
            return self.devices
        else:
            return self


beamline = HavenInstrument(
    {
        # Ophyd-async devices
        "ion_chamber": IonChamber,
        "high_heat_load_mirror": HighHeatLoadMirror,
        "kb_mirrors": KBMirrors,
        "xy_stage": XYStage,
        "table": Table,
        "aerotech_stage": AerotechStage,
        "motor": Motor,
        "energy": EnergyPositioner,
        "sim_detector": SimDetector,
        "camera": AravisDetector,
        "pss_shutter": PssShutter,
        "xspress3": Xspress3Detector,
        # Threaded ophyd devices
        "blade_slits": BladeSlits,
        "aperture_slits": ApertureSlits,
        "capillary_heater": CapillaryHeater,
        "power_supply": NHQ203MChannel,
        "synchrotron": ApsMachine,
        "robot": Robot,
        "pfcu4": PFCUFilterBank,  # <-- fails if mocked
        "dxp": make_dxp_device,
        "beamline_manager": BeamlineManager,
        "area_detector": make_area_detector,
        "scaler": MultiChannelScaler,
    },
)
