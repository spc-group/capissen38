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
        "aerotech_stage": AerotechStage,
        "camera": AravisDetector,
        "energy": EnergyPositioner,
        "high_heat_load_mirror": HighHeatLoadMirror,
        "ion_chamber": IonChamber,
        "kb_mirrors": KBMirrors,
        "motor": Motor,
        "pfcu4": PFCUFilterBank,
        "pss_shutter": PssShutter,
        "sim_detector": SimDetector,
        "table": Table,
        "xspress3": Xspress3Detector,
        "xy_stage": XYStage,
        # Threaded ophyd devices
        "blade_slits": BladeSlits,
        "aperture_slits": ApertureSlits,
        "capillary_heater": CapillaryHeater,
        "power_supply": NHQ203MChannel,
        "synchrotron": ApsMachine,
        "robot": Robot,
        "dxp": make_dxp_device,
        "beamline_manager": BeamlineManager,
        "area_detector": make_area_detector,
        "scaler": MultiChannelScaler,
    },
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
