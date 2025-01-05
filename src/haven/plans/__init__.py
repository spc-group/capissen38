"""Bluesky plans specific to spectroscopy.

Includes some standard bluesky plans with decorators.

"""

import bluesky.plans as bp

from haven.instrument import beamline
from haven.preprocessors import (
    baseline_decorator,
    open_shutters_decorator,
    shutter_suspend_decorator,
)

from ._align_motor import align_motor
from ._auto_gain import auto_gain
from ._energy_scan import energy_scan
from ._fly import fly_scan, grid_fly_scan
from ._record_dark_current import record_dark_current  # noqa: F401
from ._robot_transfer_sample import robot_transfer_sample  # noqa: F401
from ._set_energy import set_energy  # noqa: F401
from ._shutters import close_shutters, open_shutters  # noqa: F401
from ._xafs_scan import xafs_scan


def chain(*decorators):
    """Chain several decorators together into one decorator.

    Will be applied in reverse order, so the first item in *decorators* will
    be the outermost decorator.

    """

    def decorator(f):
        for d in reversed(decorators):
            f = d(f)
        return f

    return decorator


all_decorators = chain(
    shutter_suspend_decorator(), open_shutters_decorator(), baseline_decorator()
)

# Apply decorators to Haven plans
align_motor = all_decorators(align_motor)
auto_gain = all_decorators(auto_gain)
energy_scan = all_decorators(energy_scan)
fly_scan = baseline_decorator()(fly_scan)
grid_fly_scan = baseline_decorator()(grid_fly_scan)
xafs_scan = all_decorators(xafs_scan)

# Apply all_decorators to standard Bluesky plans
count = all_decorators(bp.count)
grid_scan = all_decorators(bp.grid_scan)
list_scan = all_decorators(bp.list_scan)
rel_grid_scan = all_decorators(bp.rel_grid_scan)
rel_list_scan = all_decorators(bp.rel_list_scan)
rel_scan = all_decorators(bp.rel_scan)
scan = all_decorators(bp.scan)
scan_nd = all_decorators(bp.scan_nd)

# Remove foreign imports
del beamline
del open_shutters_decorator
del baseline_decorator
del shutter_suspend_decorator
del bp

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
