import datetime as dt
import logging
import os
import time
from collections import ChainMap
from io import StringIO
from pathlib import Path

import numpy as np
import pytest

# from freezegun import freeze_time
import pytz
import time_machine
from bluesky import RunEngine
from numpy import asarray as array
from ophyd.sim import SynAxis, SynGauss, motor

from haven import XDIWriter, energy_scan, exceptions

fake_time = pytz.timezone("America/New_York").localize(
    dt.datetime(2022, 8, 19, 19, 10, 51)
)


log = logging.getLogger(__name__)
# logging.basicConfig(level=logging.DEBUG)


# Stub the epics signals in Haven

THIS_DIR = Path(__file__).parent


# Sample metadata dict
{
    "E0": 0,
    "beamline": {
        "is_connected": False,
        "name": "SPC Beamline (sector unknown)",
        "pv_prefix": "",
    },
    "detectors": ["I0", "It"],
    "edge": "Ni_K",
    "facility": {"name": "Advanced Photon Source", "xray_source": "insertion device"},
    "hints": {"dimensions": [(["energy", "exposure"], "primary")]},
    "ion_chambers": {"scaler": {"pv_prefix": ""}},
    "motors": ["energy", "exposure"],
    "num_intervals": 9,
    "num_points": 10,
    "plan_args": {
        "args": [
            (
                "SynAxis(prefix='', name='energy', "
                "read_attrs=['readback', 'setpoint'], "
                "configuration_attrs=['velocity', 'acceleration'])"
            ),
            array([8300, 8310, 8320, 8330, 8340, 8350, 8360, 8370, 8380, 8390]),
            (
                "SynAxis(prefix='', name='exposure', "
                "read_attrs=['readback', 'setpoint'], "
                "configuration_attrs=['velocity', 'acceleration'])"
            ),
            [0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1],
        ],
        "detectors": [
            (
                "SynGauss(prefix='', name='I0', "
                "read_attrs=['val'], configuration_attrs=['Imax', "
                "'center', 'sigma', 'noise', 'noise_multiplier'])"
            ),
            (
                "SynGauss(prefix='', name='It', "
                "read_attrs=['val'], configuration_attrs=['Imax', "
                "'center', 'sigma', 'noise', "
                "'noise_multiplier'])"
            ),
        ],
        "per_step": "None",
    },
    "plan_name": "list_scan",
    "plan_pattern": "inner_list_product",
    "plan_pattern_args": {
        "args": [
            (
                "SynAxis(prefix='', name='energy', "
                "read_attrs=['readback', 'setpoint'], "
                "configuration_attrs=['velocity', "
                "'acceleration'])"
            ),
            array([8300, 8310, 8320, 8330, 8340, 8350, 8360, 8370, 8380, 8390]),
            (
                "SynAxis(prefix='', name='exposure', "
                "read_attrs=['readback', 'setpoint'], "
                "configuration_attrs=['velocity', "
                "'acceleration'])"
            ),
            [0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1],
        ]
    },
    "plan_pattern_module": "bluesky.plan_patterns",
    "plan_type": "generator",
    "sample_name": "NiO_rock_salt",
    "scan_id": 1,
    "time": 1661025010.409619,
    "uid": "671c3c48-f014-421d-b3e0-57991b6745f6",
    "versions": {"bluesky": "1.8.3", "ophyd": "1.6.4"},
}


start_doc = {
    "versions": {"bluesky": "1.8.3", "ophyd": "1.6.4"},
    "detectors": ["I0", "It"],
    "d_spacing": 3.0,
    "motors": ["energy", "exposure"],
    "edge": "Ni_K",
    "facility": {
        "name": "Advanced Photon Source",
        "xray_source": "insertion device",
    },
    "beamline": {"name": "20-ID-C", "pv_prefix": "20id:"},
    "sample_name": "nickel oxide",
    "uid": "671c3c48-f014-421d-b3e0-57991b6745f6",
}
event_doc = {
    "data": {
        "I0_net_counts": 2,
        "It_net_counts": 1.5,
        "IpreKB_net_counts": 2.5,
        "Ipreslit_net_counts": 2.2,
        "Iref_net_counts": 0.56,
        "energy": 8330,
        "exposure": 0.1,
        "sim motor 1": 8330.0,
    },
    "time": 1660186828.0055554,
    "descriptor": "7ed5b8c5-045c-41fa-b79c-50fbcbe777e5",
}
descriptor_doc = {
    "hints": {
        "I0": {"fields": ["I0_net_counts"]},
        "IpreKB": {"fields": ["IpreKB_net_counts"]},
        "Ipreslit": {"fields": ["Ipreslit_net_counts"]},
        "Iref": {"fields": ["Iref_net_counts"]},
        "It": {"fields": ["It_net_counts"]},
        "sim motor 1": {"fields": ["sim motor 1"]},
        "energy": {"fields": ["energy"]},
    },
    "name": "primary",
    "run_start": "6974290f-fe3f-4535-bb8c-c29c915f88aa",
    "time": 1712865522.9266968,
    "uid": "7ed5b8c5-045c-41fa-b79c-50fbcbe777e5",
}


@pytest.fixture()
def stringio():
    yield StringIO()


@pytest.fixture()
def file_path(tmp_path):
    fp = tmp_path / "sample_file.txt"
    try:
        yield fp
    finally:
        fp.unlink()


@pytest.fixture()
def writer(stringio):
    yield XDIWriter(stringio)


def test_opens_file(file_path):
    # Pass in a string and it should hold the path until the start document is found
    fp = file_path
    writer = XDIWriter(fp)
    assert writer.fp == fp
    assert not fp.exists()
    # Run the writer
    writer("start", {"edge": "Ni_K"})
    # Check that a file was created
    assert fp.exists()


def test_uses_open_file(stringio):
    # Pass in a string and it should hold the path until the start document is found
    writer = XDIWriter(stringio)
    assert writer.fd is stringio


def test_read_only_file(file_path):
    # Check that it raises an exception if an open file has no write intent
    # Put some content in the temporary file
    with open(file_path, mode="w") as fd:
        fd.write("Hello, spam!")
    # Check that the writer raises an exception when the file is open read-only
    with open(file_path, mode="r") as fd:
        with pytest.raises(exceptions.FileNotWritable):
            XDIWriter(fd)


def test_required_headers(writer):
    writer("start", start_doc)
    writer("descriptor", descriptor_doc)
    writer("event", event_doc)  # Header gets written on first event
    # Check that required headers were added to the XDI file
    writer.fd.seek(0)
    xdi_output = writer.fd.read()
    assert "# XDI/1.0 bluesky/1.8.3 ophyd/1.6.4" in xdi_output
    assert "# Column.1: energy" in xdi_output
    assert "# Element.symbol: Ni" in xdi_output
    assert "# Element.edge: K" in xdi_output
    assert "# Mono.d_spacing: 3" in xdi_output  # Not implemented yet
    assert "# -------------" in xdi_output


@time_machine.travel(fake_time)
def test_optional_headers(writer):
    os.environ["TZ"] = "America/New_York"
    time.tzset()
    writer("start", start_doc)
    writer("descriptor", descriptor_doc)
    writer("event", event_doc)
    # Check that required headers were added to the XDI file
    writer.fd.seek(0)
    xdi_output = writer.fd.read()
    expected_metadata = {
        "Facility.name": "Advanced Photon Source",
        "Facility.xray_source": "insertion device",
        "Beamline.name": "20-ID-C",
        "Beamline.pv_prefix": "20id:",
        "Scan.start_time": "2022-08-19 19:10:51-0400",
        "Column.8": "time",
        "uid": "671c3c48-f014-421d-b3e0-57991b6745f6",
    }
    for key, val in expected_metadata.items():
        assert f"# {key.lower()}: {val.lower()}\n" in xdi_output.lower()


@time_machine.travel(fake_time)
def test_file_path_formatting(tmp_path):
    """Check that "{date}_{user}.xdi" formatting works in the filename."""
    writer = XDIWriter(tmp_path / "{year}{month}{day}_{short_uid}_{sample_name}.xdi")
    writer.start(start_doc)
    assert str(writer.fp) == str(tmp_path / "20220819_671c3c48_nickel-oxide.xdi")


@time_machine.travel(fake_time)
def test_file_path_reentry(tmp_path):
    """Check that "{date}_{user}.xdi" formatting can be used multiple times."""
    # Start the writer once with basic arguments
    writer = XDIWriter(tmp_path / "{year}{month}{day}_{short_uid}_{sample_name}.xdi")
    writer.start(start_doc)
    target_path = str(tmp_path / "20220819_671c3c48_nickel-oxide.xdi")
    assert str(writer.fp) == target_path
    assert writer.fd.name == target_path
    # Check that additional start docs don't create new files
    writer.start(start_doc)
    # Start the writer again with a second set of arguments
    new_start_doc = ChainMap(
        {
            "sample_name": "manganese oxide",
            "uid": "a6842eaa-6dd3-4666-83a0-1829cd687556",
        },
        start_doc,
    )
    writer.start(new_start_doc)
    target_path = str(tmp_path / "20220819_a6842eaa_manganese-oxide.xdi")
    assert str(writer.fp) == target_path
    assert writer.fd.name == target_path


@time_machine.travel(fake_time)
def test_secondary_stream(tmp_path):
    """Check that secondary data streams get ignored."""
    sec_event = ChainMap(
        {
            "descriptor": "b1006389-fd92-4037-9eb3-02332703552b",
            "data": {"Iref": 2},
        },
        event_doc,
    )
    sec_descriptor = ChainMap(
        {"uid": sec_event["descriptor"], "name": "secondary"}, descriptor_doc
    )
    # Set up the writer
    writer = XDIWriter(tmp_path / "{year}{month}{day}_{short_uid}_{sample_name}.xdi")
    writer.start(start_doc)
    # Events before the descriptor should raise exceptions
    assert writer._primary_uid == None
    with pytest.raises(exceptions.DocumentNotFound):
        writer.event(event_doc)
    # Prime the writer with descriptor documents
    writer.descriptor(descriptor_doc)
    writer.descriptor(sec_descriptor)
    # Send a correct primary data event
    writer.event(event_doc)
    # Send an event from secondary data stream
    writer.event(sec_event)


@time_machine.travel(fake_time)
def test_manager_path(tmp_path, beamline_manager):
    """Check that "{manager_path}.xdi" formatting works in the filename."""
    # Set up a full path on the beamline manager
    beamline_manager.local_storage.full_path._readback = str(tmp_path) + "/"
    # Create the XDI writer object
    writer = XDIWriter(
        "{manager_path}/{year}{month}{day}_{short_uid}_{sample_name}.xdi"
    )
    writer.start(start_doc)
    assert str(writer.fp) == f"{tmp_path}/20220819_671c3c48_nickel-oxide.xdi"


def test_file_path_formatting_bad_key():
    """Check that "{date}_{user}.xdi" raises exception if placeholder is invalid."""
    writer = XDIWriter("{year}{month}{day}_{spam}_{sample_name}.xdi")
    with pytest.raises(exceptions.XDIFilenameKeyNotFound):
        writer.start(start_doc)


def test_data(writer):
    """Check that the TSV data section is present and correct."""
    writer.start(start_doc)
    writer.descriptor(descriptor_doc)
    writer("event", event_doc)
    # Verify the data were written properly
    writer.fd.seek(0)
    xdi_output = writer.fd.read()
    assert "8330" in xdi_output
    assert "1660186828.0055554" in xdi_output


def test_with_plan(stringio, sim_registry, event_loop, beamline_manager, tmp_path):
    beamline_manager.local_storage.full_path._readback = str(tmp_path) + "/"
    I0 = SynGauss(
        "I0",
        motor,
        "motor",
        center=-0.5,
        Imax=1,
        sigma=1,
        labels={"detectors"},
    )
    It = SynGauss(
        "It",
        motor,
        "motor",
        center=-0.5,
        Imax=1,
        sigma=1,
        labels={"detectors"},
    )
    energy_motor = SynAxis(name="energy", labels={"motors", "energies"})
    exposure = SynAxis(name="exposure", labels={"motors", "exposures"})
    writer = XDIWriter(stringio)
    RE = RunEngine()
    energy_plan = energy_scan(
        np.arange(8300.0, 8400.0, 10),
        detectors=[I0, It],
        E0="Ni_K",
        energy_signals=[energy_motor],
        time_signals=[exposure],
        md=dict(sample_name="NiO_rock_salt"),
    )
    RE(energy_plan, writer)


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
