__all__ = ["energy_scan"]

__version__ = "0.1.0"

# Force ophyd to use caproto as its backend
# import ophyd
# ophyd.set_cl("caproto")

from . import plans  # noqa: F401
from ._iconfig import load_config  # noqa: F401

#  Top-level imports
# from .catalog import load_catalog, load_data, load_result, tiled_client  # noqa: F401
from .catalog import catalog  # noqa: F401
from .constants import edge_energy  # noqa: F401
from .energy_ranges import ERange, KRange, merge_ranges  # noqa: F401
from .instrument import (  # noqa: F401
    InstrumentRegistry,
    IonChamber,
    Monochromator,
    Robot,
    ion_chamber,
    load_robots,
    registry,
)
from .instrument.device import RegexComponent  # noqa: F401
from .instrument.dxp import load_dxp_detectors  # noqa: F401
from .instrument.load_instrument import load_instrument  # noqa: F401
from .instrument.motor import HavenMotor  # noqa: F401
from .instrument.xspress import load_xspress_detectors  # noqa: F401
from .motor_position import (  # noqa: F401
    get_motor_position,
    list_current_motor_positions,
    list_motor_positions,
    recall_motor_position,
    save_motor_position,
)
from .plans.align_motor import align_motor, align_pitch2  # noqa: F401
from .plans.align_slits import align_slits  # noqa: F401
from .plans.auto_gain import GainRecommender, auto_gain  # noqa:F401
from .plans.beam_properties import fit_step  # noqa: F401
from .plans.beam_properties import knife_scan  # noqa: F401
from .plans.energy_scan import energy_scan  # noqa: F401
from .plans.fly import fly_scan, grid_fly_scan  # noqa: F401
from .plans.mono_gap_calibration import calibrate_mono_gap  # noqa: F401
from .plans.mono_ID_calibration import mono_ID_calibration  # noqa: F401
from .plans.record_dark_current import record_dark_current  # noqa: F401
from .plans.robot_transfer_sample import robot_transfer_sample  # noqa: F401
from .plans.set_energy import set_energy  # noqa: F401
from .plans.shutters import close_shutters, open_shutters  # noqa: F401
from .plans.xafs_scan import xafs_scan  # noqa: F401
from .preprocessors import (  # noqa: F401
    baseline_decorator,
    baseline_wrapper,
    shutter_suspend_decorator,
    shutter_suspend_wrapper,
)
from .progress_bar import ProgressBar  # noqa: F401
from .run_engine import run_engine  # noqa: F401
from .xdi_writer import XDIWriter  # noqa: F401

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
