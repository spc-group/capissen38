import uuid
from typing import Sequence

from bluesky import Msg
from bluesky import plan_stubs as bps
from ophyd import Device

from ..devices.shutter import ShutterState
from ..instrument import beamline
from ._shutters import close_shutters, open_shutters


def count_is_complete(*, old_value, value, **kwargs):
    """Check if the value is done."""
    was_running = old_value == 1
    is_running_now = value == 1
    is_done = was_running and not is_running_now
    print(is_done)
    return is_done


def record_dark_current(
    ion_chambers: Sequence[Device], shutters: Sequence[Device] = []
):
    """Record the dark current on the ion chambers.

    - Close shutters
    - Record ion chamber dark current
    - Restore shutters to their previous positions

    Parameters
    ==========
    ion_chambers
      Ion chamber devices or names.
    shutters
      Shutter devices or names. These shutters will be closed before
      recording the dark current, and then be returned to its original
      state afterward recording the dark current.

    """
    # Get previous shutter states
    old_shutters = {}
    for shutter in shutters:
        old_shutters[shutter] = yield from bps.rd(shutter.readback)
    # Close shutters
    yield from close_shutters(shutters)
    # Measure the dark current
    ion_chambers = beamline.devices.findall(ion_chambers)
    # Record dark currents
    group = uuid.uuid4()
    for ic in ion_chambers:
        yield Msg("trigger", ic, group=group, record_dark_current=True)
        # yield from bps.trigger(ic.record_dark_current, group=group, wait=False)
    # Wait for the devices to be done recording dark current
    yield from bps.wait(group=group)
    # Reset shutters to their original states
    to_open = [
        sht for sht, old_state in old_shutters.items() if old_state == ShutterState.OPEN
    ]
    yield from open_shutters(to_open)


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
