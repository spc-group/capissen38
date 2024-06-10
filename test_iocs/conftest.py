# import os
# import warnings
# from pathlib import Path
# from unittest.mock import MagicMock
# from types import SimpleNamespace
# from collections import OrderedDict
# from subprocess import Popen, TimeoutExpired, PIPE
# import subprocess
# import shutil
# import time
# from unittest import mock
# import asyncio

# import pytest

# import ophyd
# from ophyd import DynamicDeviceComponent as DDC, Kind
# from ophyd.sim import (
#     instantiate_fake_device,
#     make_fake_device,
#     fake_device_cache,
#     FakeEpicsSignal,
# )
# from pydm.data_plugins import add_plugin

# import haven
# from haven.simulated_ioc import simulated_ioc
# from haven import load_config, registry
# from haven._iconfig import beamline_connected as _beamline_connected
# from haven.instrument.aerotech import AerotechFlyer, AerotechStage
# from haven.instrument.aps import ApsMachine
# from haven.instrument.shutter import Shutter
# from haven.instrument.camera import AravisDetector
# from haven.instrument.delay import EpicsSignalWithIO
# from haven.instrument.dxp import DxpDetector, add_mcas as add_dxp_mcas
# from haven.instrument.ion_chamber import IonChamber
# from haven.instrument.xspress import Xspress3Detector, add_mcas as add_xspress_mcas
# from firefly.application import FireflyApplication
# from firefly.ophyd_plugin import OphydPlugin
# from firefly.main_window import FireflyMainWindow


# # IOC_SCOPE = "function"
# IOC_SCOPE = "session"


# @pytest.fixture(scope=IOC_SCOPE)
# def ioc_undulator(request):
#     prefix = "ID255:"
#     pvs = dict(energy=f"{prefix}Energy.VAL")
#     return run_fake_ioc(
#         module_name="haven.tests.ioc_undulator",
#         name="Fake undulator IOC",
#         prefix=prefix,
#         pvs=pvs,
#         pv_to_check=pvs["energy"],
#         request=request,
#     )


# @pytest.fixture(scope=IOC_SCOPE)
# def ioc_camera(request):
#     prefix = "255idgigeA:"
#     pvs = dict(
#         cam_acquire=f"{prefix}cam1:Acquire",
#         cam_acquire_busy=f"{prefix}cam1:AcquireBusy",
#     )
#     return run_fake_ioc(
#         module_name="haven.tests.ioc_area_detector",
#         name="Fake IOC for a simulated machine vision camera",
#         prefix=prefix,
#         pvs=pvs,
#         pv_to_check=pvs["cam_acquire_busy"],
#         request=request,
#     )


# @pytest.fixture(scope=IOC_SCOPE)
# def ioc_area_detector(request):
#     prefix = "255idSimDet:"
#     pvs = dict(
#         cam_acquire=f"{prefix}cam1:Acquire",
#         cam_acquire_busy=f"{prefix}cam1:AcquireBusy",
#     )
#     return run_fake_ioc(
#         module_name="haven.tests.ioc_area_detector",
#         name="Fake IOC for a simulated area detector",
#         prefix=prefix,
#         pvs=pvs,
#         pv_to_check=pvs["cam_acquire_busy"],
#         request=request,
#     )


# @pytest.fixture(scope=IOC_SCOPE)
# def ioc_bss(request):
#     prefix = "255idc:bss:"
#     pvs = dict(
#         esaf_id=f"{prefix}esaf:id",
#         esaf_cycle=f"{prefix}esaf:cycle",
#         proposal_id=f"{prefix}proposal:id",
#     )
#     return run_fake_ioc(
#         module_name="haven.tests.ioc_apsbss",
#         name="Fake IOC for APS beamline scheduling system (BSS)",
#         prefix=prefix,
#         pvs=pvs,
#         pv_to_check=pvs["esaf_cycle"],
#         request=request,
#     )


# def run_fake_ioc(
#     module_name,
#     prefix: str,
#     request,
#     name="Fake IOC",
#     pvs=None,
#     pv_to_check: str = None,
# ):
#     if pvs is None:
#         pvs = {}
#     pytest.importorskip("caproto.tests.conftest")
#     from caproto.tests.conftest import run_example_ioc, poll_readiness

#     process = run_example_ioc(
#         module_name=module_name,
#         request=request,
#         pv_to_check=None,
#         args=("--prefix", prefix, "--list-pvs", "-v"),
#         very_verbose=False,
#     )
#     # Verify the IOC started
#     if pv_to_check is not None:
#         poll_timeout, poll_attempts = 1.0, 30
#         poll_readiness(
#             pv_to_check, timeout=poll_timeout, attempts=poll_attempts, process=process
#         )
#     return SimpleNamespace(
#         process=process, prefix=prefix, name=name, pvs=pvs, type="caproto"
#     )


# @pytest.fixture(scope=IOC_SCOPE)
# def ioc_scaler(request):
#     prefix = "255idVME:scaler1"
#     pvs = dict(calc=f"{prefix}_calc2.VAL")
#     return run_fake_ioc(
#         module_name="haven.tests.ioc_scaler",
#         name="Fake scaler IOC",
#         prefix=prefix,
#         pvs=pvs,
#         pv_to_check=pvs["calc"],
#         request=request,
#     )


# @pytest.fixture(scope=IOC_SCOPE)
# def ioc_ptc10(request):
#     prefix = "255idptc10:"
#     pvs = dict(
#         pid1_voltage=f"{prefix}5A:output",
#         pid1_voltage_rbv=f"{prefix}5A:output_RBV",
#         tc1_temperature=f"{prefix}2A:temperature",
#     )
#     return run_fake_ioc(
#         module_name="haven.tests.ioc_ptc10",
#         name="Fake PTC10 temperature controller IOC",
#         prefix=prefix,
#         pvs=pvs,
#         pv_to_check=pvs["tc1_temperature"],
#         request=request,
#     )


# @pytest.fixture(scope="session")
# def pydm_ophyd_plugin():
#     return add_plugin(OphydPlugin)


# @pytest.fixture(scope=IOC_SCOPE)
# def ioc_motor(request):
#     prefix = "255idVME:"
#     pvs = dict(m1=f"{prefix}m1", m2=f"{prefix}m2", m3=f"{prefix}m3", m4=f"{prefix}m4")
#     return run_fake_ioc(
#         module_name="haven.tests.ioc_motor",
#         name="Fake motor IOC",
#         prefix=prefix,
#         pvs=pvs,
#         pv_to_check=pvs["m1"],
#         request=request,
#     )


# @pytest.fixture(scope=IOC_SCOPE)
# def ioc_preamp(request):
#     prefix = "255idc:"
#     pvs = dict(
#         preamp1_sens_num=f"{prefix}SR01:sens_num",
#         preamp2_sens_num=f"{prefix}SR02:sens_num",
#         preamp3_sens_num=f"{prefix}SR03:sens_num",
#         preamp4_sens_num=f"{prefix}SR04:sens_num",
#         preamp1_sens_unit=f"{prefix}SR01:sens_unit",
#         preamp2_sens_unit=f"{prefix}SR02:sens_unit",
#         preamp3_sens_unit=f"{prefix}SR03:sens_unit",
#         preamp4_sens_unit=f"{prefix}SR04:sens_unit",
#         preamp1_offset_num=f"{prefix}SR01:offset_num",
#         preamp2_offset_num=f"{prefix}SR02:offset_num",
#         preamp3_offset_num=f"{prefix}SR03:offset_num",
#         preamp4_offset_num=f"{prefix}SR04:offset_num",
#         preamp1_offset_unit=f"{prefix}SR01:offset_unit",
#         preamp2_offset_unit=f"{prefix}SR02:offset_unit",
#         preamp3_offset_unit=f"{prefix}SR03:offset_unit",
#         preamp4_offset_unit=f"{prefix}SR04:offset_unit",
#     )
#     return run_fake_ioc(
#         module_name="haven.tests.ioc_preamp",
#         name="Fake preamp IOC",
#         prefix=prefix,
#         pvs=pvs,
#         pv_to_check=pvs["preamp1_sens_num"],
#         request=request,
#     )


# @pytest.fixture(scope=IOC_SCOPE)
# def ioc_simple(request):
#     prefix = "simple:"
#     pvs = dict(
#         A=f"{prefix}A",
#         B=f"{prefix}B",
#         C=f"{prefix}C",
#     )
#     pv_to_check = pvs["A"]
#     return run_fake_ioc(
#         module_name="haven.tests.ioc_simple",
#         name="Fake simple IOC",
#         prefix=prefix,
#         pvs=pvs,
#         pv_to_check=pv_to_check,
#         request=request,
#     )


# @pytest.fixture(scope=IOC_SCOPE)
# def ioc_mono(request):
#     prefix = "255idMono:"
#     pvs = dict(
#         bragg=f"{prefix}ACS:m3",
#         energy=f"{prefix}Energy",
#         id_tracking=f"{prefix}ID_tracking",
#         id_offset=f"{prefix}ID_offset",
#     )
#     return run_fake_ioc(
#         module_name="haven.tests.ioc_mono",
#         name="Fake mono IOC",
#         prefix=prefix,
#         pvs=pvs,
#         pv_to_check=pvs["energy"],
#         request=request,
#     )


# @pytest.fixture(scope=IOC_SCOPE)
# def ioc_dxp(request):
#     prefix = "255idDXP:"
#     pvs = dict(acquiring=f"{prefix}Acquiring")
#     return run_fake_ioc(
#         module_name="haven.tests.ioc_dxp",
#         name="Fake DXP-based detector IOC",
#         prefix=prefix,
#         pvs=pvs,
#         pv_to_check=pvs["acquiring"],
#         request=request,
#     )


# # Simulated devices
# @pytest.fixture()
# def queue_app(ffapp):
#     """An application that is set up to interact (fakely) with the queue
#     server.

#     """
#     warnings.warn("queue_app is deprecated, just use ffapp instead.")
#     return ffapp


# @pytest.fixture()
# def sim_vortex(dxp):
#     warnings.warn("sim_vortex is deprecated, just use ``dxp`` instead.")
#     return dxp
