from typing import Sequence, Union

from bluesky import plan_stubs as bps
from ophyd import Device

from ..devices.shutter import ShutterState
from ..instrument import beamline


def _set_shutters(shutters: Union[str, Sequence[Device]], direction: int):
    if shutters != []:
        shutters = beamline.devices.findall(shutters)
    # Prepare the plan
    plan_args = [obj for shutter in shutters for obj in (shutter, direction)]
    if len(plan_args) > 0:
        # Emit the messages
        yield from bps.mv(*plan_args)


def open_shutters(shutters: Union[str, Sequence[Device]]):
    """A plan to open the shutters.

    By default, this plan is greedy and will open all shutters defined
    at the beamline. If only specific shutters should be opened, they
    can be passed either as Device objects or device names as the
    *shutters* argument.

    E.g.
      RE(open_shutters(["endstation_shutter"]))

    E.g.
      shutter = haven.devices.shutter.Shutter(..., name="Shutter C")
      RE(open_shutters([shutter]))

    This plan will temporarily remove the default shutter-related
    suspenders from the haven run engine.

    """
    yield from _set_shutters(shutters, ShutterState.OPEN)


def close_shutters(shutters: Union[str, Sequence[Device]] = "shutters"):
    """A plan to close some shutters.

    By default, this plan is lazy and requires any shutters to be
    passed explicitly. Shutters can be passed either as Device objects
    or device names as the *shutters* argument.

    E.g.
      RE(close_shutters(["Shutter C"]))

    E.g.
      shutter = haven.devices.shutter.Shutter(..., name="Shutter C")
      RE(close_shutters([shutter]))

    This plan will temporarily remove the default shutter-related
    suspenders from the haven run engine.

    """
    yield from _set_shutters(shutters, ShutterState.CLOSED)


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
