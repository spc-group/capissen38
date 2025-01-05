"""The Haven beamline control system.

See https://haven-spc.readthedocs.io for full documentation."""

__all__ = [
    "energy_scan",
    "xafs_scan",
]

# Get installed version number
import importlib.metadata

try:
    __version__ = importlib.metadata.version("haven-spc")
except importlib.metadata.PackageNotFoundError:
    import pkg_resources

    __version__ = pkg_resources.get_distribution("haven-spc").version
    del pkg_resources
finally:
    del importlib


# Determine the file path of the ipython startup file
from pathlib import Path

ipython_startup_file = Path(__file__).parent / "ipython_startup.ipy"
del Path


# Force ophyd to use caproto as its backend
# import ophyd
# ophyd.set_cl("caproto")

from . import plans  # noqa: F401
from ._iconfig import load_config  # noqa: F401

#  Top-level imports
# from .catalog import load_catalog, load_data, load_result, tiled_client  # noqa: F401
from .catalog import load_catalog, tiled_client  # noqa: F401
from .constants import edge_energy  # noqa: F401
from .devices import IonChamber, Monochromator, Robot, ion_chamber  # noqa: F401
from .devices.motor import HavenMotor  # noqa: F401
from .energy_ranges import ERange, KRange, merge_ranges  # noqa: F401
from .instrument import beamline  # noqa: F401
from .motor_position import (  # noqa: F401
    get_motor_position,
    list_current_motor_positions,
    list_motor_positions,
    recall_motor_position,
    save_motor_position,
)
from .preprocessors import (  # noqa: F401
    baseline_decorator,
    baseline_wrapper,
    open_shutters_decorator,
    open_shutters_wrapper,
    shutter_suspend_decorator,
    shutter_suspend_wrapper,
)
from .progress_bar import ProgressBar  # noqa: F401
from .run_engine import run_engine  # noqa: F401
from .utils import sanitize_name  # noqa: F401

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
