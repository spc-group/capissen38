import os
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

# from pydm.data_plugins import plugin_modules, add_plugin
import pytest
from apstools.devices.srs570_preamplifier import GainSignal
from ophyd import DynamicDeviceComponent as DCpt
from ophyd import Kind
from ophyd.sim import (
    FakeEpicsSignal,
    fake_device_cache,
    instantiate_fake_device,
    make_fake_device,
)
from tiled.adapters.mapping import MapAdapter
from tiled.adapters.xarray import DatasetAdapter
from tiled.client import Context, from_context
from tiled.server.app import build_app

import haven
from haven._iconfig import beamline_connected as _beamline_connected
from haven.catalog import Catalog
from haven.instrument.aerotech import AerotechStage
from haven.instrument.aps import ApsMachine
from haven.instrument.beamline_manager import BeamlineManager, IOCManager
from haven.instrument.camera import AravisDetector
from haven.instrument.delay import EpicsSignalWithIO
from haven.instrument.dxp import DxpDetector
from haven.instrument.dxp import add_mcas as add_dxp_mcas
from haven.instrument.ion_chamber import IonChamber
from haven.instrument.monochromator import Monochromator
from haven.instrument.robot import Robot
from haven.instrument.shutter import Shutter
from haven.instrument.slits import ApertureSlits, BladeSlits
from haven.instrument.xia_pfcu import PFCUFilter, PFCUFilterBank, PFCUShutter
from haven.instrument.xspress import Xspress3Detector
from haven.instrument.xspress import add_mcas as add_xspress_mcas

top_dir = Path(__file__).parent.resolve()
haven_dir = top_dir / "haven"


def pytest_configure():
    haven.registry.auto_register = False


# Specify the configuration files to use for testing
os.environ["HAVEN_CONFIG_FILES"] = ",".join(
    [
        f"{haven_dir/'iconfig_testing.toml'}",
        f"{haven_dir/'iconfig_default.toml'}",
    ]
)


class FakeEpicsSignalWithIO(FakeEpicsSignal):
    # An EPICS signal that simply uses the DG-645 convention of
    # 'AO' being the setpoint and 'AI' being the read-back
    _metadata_keys = EpicsSignalWithIO._metadata_keys

    def __init__(self, prefix, **kwargs):
        super().__init__(f"{prefix}I", write_pv=f"{prefix}O", **kwargs)


# Ophyd uses a cache of signals and their corresponding fakes
# We need to add ours in so they get simulated properly.
fake_device_cache[EpicsSignalWithIO] = FakeEpicsSignalWithIO
fake_device_cache[GainSignal] = FakeEpicsSignal


@pytest.fixture()
def beamline_connected():
    with _beamline_connected(True):
        yield


@pytest.fixture()
def sim_registry(monkeypatch):
    # Save the registry so we can restore it later
    registry = haven.registry
    objects_by_name = registry._objects_by_name
    objects_by_label = registry._objects_by_label
    registry.clear()
    registry.auto_register = True
    # Run the test
    try:
        yield registry
    finally:
        # Restore the previous registry components
        registry.auto_register = False
        registry.clear()
        registry._objects_by_name = objects_by_name
        registry._objects_by_label = objects_by_label


@pytest.fixture()
def sim_ion_chamber(sim_registry):
    FakeIonChamber = make_fake_device(IonChamber)
    ion_chamber = FakeIonChamber(
        prefix="scaler_ioc",
        name="I00",
        labels={"ion_chambers"},
        ch_num=2,
    )
    # Set metadata
    preamp = ion_chamber.preamp
    preamp.sensitivity_value._enum_strs = tuple(preamp.values)
    preamp.sensitivity_unit._enum_strs = tuple(preamp.units)
    preamp.offset_value._enum_strs = tuple(preamp.values)
    preamp.offset_unit._enum_strs = tuple(preamp.offset_units)
    preamp.gain_mode._enum_strs = ("LOW NOISE", "HIGH BW", "LOW DRIFT")
    preamp.gain_mode.set("LOW NOISE").wait(timeout=3)
    return ion_chamber


@pytest.fixture()
def I0(sim_registry):
    """A fake ion chamber named 'I0' on scaler channel 2."""
    FakeIonChamber = make_fake_device(IonChamber)
    ion_chamber = FakeIonChamber(
        prefix="scaler_ioc",
        preamp_prefix="preamp_ioc:SR04:",
        name="I0",
        labels={"ion_chambers"},
        ch_num=2,
    )
    return ion_chamber


@pytest.fixture()
def It(sim_registry):
    """A fake ion chamber named 'It' on scaler channel 3."""
    FakeIonChamber = make_fake_device(IonChamber)
    ion_chamber = FakeIonChamber(
        prefix="scaler_ioc", name="It", labels={"ion_chambers"}, ch_num=3
    )
    return ion_chamber


@pytest.fixture()
def blade_slits(sim_registry):
    """A fake set of slits using the 4-blade setup."""
    FakeSlits = make_fake_device(BladeSlits)
    slits = FakeSlits(prefix="255idc:KB_slits", name="kb_slits", labels={"slits"})
    return slits


class SimpleBeamlineManager(BeamlineManager):
    """For a fake class, we need to un-override __new__ to just make
    itself.

    """

    iocs = DCpt(
        {
            "ioc255idb": (IOCManager, "ioc255idb:", {}),
            "ioc255idc": (IOCManager, "ioc255idc:", {}),
        }
    )

    def __new__(cls, *args, **kwargs):
        return object.__new__(cls)


@pytest.fixture()
def beamline_manager(sim_registry):
    """A fake set of slits using the 4-blade setup."""
    FakeManager = make_fake_device(SimpleBeamlineManager)
    manager = FakeManager(
        prefix="companionCube:", name="companion_cube", labels={"beamline_manager"}
    )
    return manager


@pytest.fixture()
def aperture_slits(sim_registry):
    """A fake slit assembling using the rotary aperture design."""
    FakeSlits = make_fake_device(ApertureSlits)
    slits = FakeSlits(
        prefix="255ida:slits:US:",
        name="whitebeam_slits",
        pitch_motor="m3",
        yaw_motor="m4",
        horizontal_motor="m1",
        diagonal_motor="m2",
        labels={"slits"},
    )
    return slits


@pytest.fixture()
def sim_camera(sim_registry):
    FakeCamera = make_fake_device(AravisDetector)
    camera = FakeCamera(name="s255id-gige-A", labels={"cameras", "area_detectors"})
    camera.pva.pv_name._readback = "255idSimDet:Pva1:Image"
    # Registry with the simulated registry
    yield camera


class DxpVortex(DxpDetector):
    mcas = DCpt(
        add_dxp_mcas(range_=[0, 1, 2, 3]),
        kind=Kind.normal | Kind.hinted,
        default_read_attrs=[f"mca{i}" for i in [0, 1, 2, 3]],
        default_configuration_attrs=[f"mca{i}" for i in [0, 1, 2, 3]],
    )


@pytest.fixture()
def dxp(sim_registry):
    FakeDXP = make_fake_device(DxpVortex)
    vortex = FakeDXP(name="vortex_me4", labels={"xrf_detectors", "detectors"})
    # vortex.net_cdf.dimensions.set([1477326, 1, 1])
    yield vortex


class Xspress3Vortex(Xspress3Detector):
    mcas = DCpt(
        add_xspress_mcas(range_=[0, 1, 2, 3]),
        kind=Kind.normal | Kind.hinted,
        default_read_attrs=[f"mca{i}" for i in [0, 1, 2, 3]],
        default_configuration_attrs=[f"mca{i}" for i in [0, 1, 2, 3]],
    )


@pytest.fixture()
def xspress(sim_registry):
    FakeXspress = make_fake_device(Xspress3Vortex)
    vortex = FakeXspress(name="vortex_me4", labels={"xrf_detectors"})
    yield vortex


@pytest.fixture()
def aerotech():
    Stage = make_fake_device(
        AerotechStage,
    )
    stage = Stage(
        "255id",
        delay_prefix="255id:DG645",
        pv_horiz=":m1",
        pv_vert=":m2",
        name="aerotech",
    )
    return stage


@pytest.fixture()
def robot():
    RobotClass = make_fake_device(Robot)
    robot = RobotClass(name="robotA", prefix="255idA:")
    return robot


@pytest.fixture()
def aerotech_flyer(aerotech):
    flyer = aerotech.horiz
    flyer.user_setpoint._limits = (0, 1000)
    flyer.send_command = mock.MagicMock()
    yield flyer


@pytest.fixture()
def mono(sim_registry):
    mono = instantiate_fake_device(Monochromator, name="monochromator")
    yield mono


@pytest.fixture()
def aps(sim_registry):
    aps = instantiate_fake_device(ApsMachine, name="APS")
    yield aps


@pytest.fixture()
def xia_shutter_bank(sim_registry):
    class ShutterBank(PFCUFilterBank):
        shutters = DCpt(
            {
                "shutter_0": (
                    PFCUShutter,
                    "",
                    {"top_filter": 4, "bottom_filter": 3, "labels": {"shutters"}},
                )
            }
        )

        def __new__(cls, *args, **kwargs):
            return object.__new__(cls)

    FakeBank = make_fake_device(ShutterBank)
    bank = FakeBank(prefix="255id:pfcu4:", name="xia_filter_bank", shutters=[[3, 4]])
    yield bank


@pytest.fixture()
def xia_shutter(xia_shutter_bank):
    yield xia_shutter_bank.shutters.shutter_0


@pytest.fixture()
def shutters(sim_registry):
    FakeShutter = make_fake_device(Shutter)
    kw = dict(
        prefix="_prefix",
        open_pv="_prefix",
        close_pv="_prefix2",
        state_pv="_prefix2",
        labels={"shutters"},
    )
    shutters = [
        FakeShutter(name="Shutter A", **kw),
        FakeShutter(name="Shutter C", **kw),
    ]
    yield shutters


@pytest.fixture()
def filters(sim_registry):
    FakeFilter = make_fake_device(PFCUFilter)
    kw = {
        "labels": {"filters"},
    }
    filters = [
        FakeFilter(name="Filter A", prefix="filter1", **kw),
        FakeFilter(name="Filter B", prefix="filter2", **kw),
    ]
    return filters


# holds a global QApplication instance created in the qapp fixture; keeping
# this reference alive avoids it being garbage collected too early
_ffapp_instance = None


# Tiled data to use for testing
# Some mocked test data
run1 = pd.DataFrame(
    {
        "energy_energy": np.linspace(8300, 8400, num=100),
        "It_net_counts": np.abs(np.sin(np.linspace(0, 4 * np.pi, num=100))),
        "I0_net_counts": np.linspace(1, 2, num=100),
    }
).to_xarray()

grid_scan = pd.DataFrame(
    {
        "CdnIPreKb": np.linspace(0, 104, num=105),
        "It_net_counts": np.linspace(0, 104, num=105),
        "aerotech_horiz": np.linspace(0, 104, num=105),
        "aerotech_vert": np.linspace(0, 104, num=105),
    }
).to_xarray()

hints = {
    "energy": {"fields": ["energy_energy", "energy_id_energy_readback"]},
}

bluesky_mapping = {
    "7d1daf1d-60c7-4aa7-a668-d1cd97e5335f": MapAdapter(
        {
            "primary": MapAdapter(
                {
                    "data": DatasetAdapter.from_dataset(run1),
                },
                metadata={"descriptors": [{"hints": hints}]},
            ),
        },
        metadata={
            "plan_name": "xafs_scan",
            "start": {
                "plan_name": "xafs_scan",
                "uid": "7d1daf1d-60c7-4aa7-a668-d1cd97e5335f",
                "hints": {"dimensions": [[["energy_energy"], "primary"]]},
            },
        },
    ),
    "9d33bf66-9701-4ee3-90f4-3be730bc226c": MapAdapter(
        {
            "primary": MapAdapter(
                {
                    "data": DatasetAdapter.from_dataset(run1),
                },
                metadata={"descriptors": [{"hints": hints}]},
            ),
        },
        metadata={
            "start": {
                "plan_name": "rel_scan",
                "uid": "9d33bf66-9701-4ee3-90f4-3be730bc226c",
                "hints": {"dimensions": [[["pitch2"], "primary"]]},
            }
        },
    ),
    # 2D grid scan map data
    "85573831-f4b4-4f64-b613-a6007bf03a8d": MapAdapter(
        {
            "primary": MapAdapter(
                {
                    "data": DatasetAdapter.from_dataset(grid_scan),
                },
                metadata={
                    "descriptors": [
                        {
                            "hints": {
                                "Ipreslit": {"fields": ["Ipreslit_net_counts"]},
                                "CdnIPreKb": {"fields": ["CdnIPreKb_net_counts"]},
                                "I0": {"fields": ["I0_net_counts"]},
                                "CdnIt": {"fields": ["CdnIt_net_counts"]},
                                "aerotech_vert": {"fields": ["aerotech_vert"]},
                                "aerotech_horiz": {"fields": ["aerotech_horiz"]},
                                "Ipre_KB": {"fields": ["Ipre_KB_net_counts"]},
                                "CdnI0": {"fields": ["CdnI0_net_counts"]},
                                "It": {"fields": ["It_net_counts"]},
                            }
                        }
                    ]
                },
            ),
        },
        metadata={
            "start": {
                "plan_name": "grid_scan",
                "uid": "85573831-f4b4-4f64-b613-a6007bf03a8d",
                "hints": {
                    "dimensions": [
                        [["aerotech_vert"], "primary"],
                        [["aerotech_horiz"], "primary"],
                    ],
                    "gridding": "rectilinear",
                },
                "shape": [5, 21],
                "extents": [[-80, 80], [-100, 100]],
            },
        },
    ),
}


mapping = {
    "255id_testing": MapAdapter(bluesky_mapping),
}

tree = MapAdapter(mapping)


@pytest.fixture(scope="session")
def tiled_client():
    app = build_app(tree)
    with Context.from_app(app) as context:
        client = from_context(context)
        yield client["255id_testing"]


@pytest.fixture(scope="session")
def catalog(tiled_client):
    return Catalog(client=tiled_client)


# -----------------------------------------------------------------------------
# :author:    Mark Wolfman
# :email:     wolfman@anl.gov
# :copyright: Copyright © 2023, UChicago Argonne, LLC
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
