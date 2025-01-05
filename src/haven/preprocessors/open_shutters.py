from bluesky import plan_stubs as bps
from bluesky.preprocessors import finalize_wrapper
from bluesky.utils import make_decorator
from ophydregistry import Registry

from haven.devices.shutter import ShutterState
from haven.instrument import beamline

__all__ = ["open_shutters_wrapper", "open_shutters_decorator"]


def _can_open(shutter):
    return getattr(shutter, "allow_open", True) and getattr(
        shutter, "allow_close", True
    )


def _set_shutters(shutters, state: int):
    """A plan stub that sets all shutters to the given state."""
    mv_args = [val for shutter in shutters for val in (shutter, state)]
    if len(mv_args) > 0:
        return (yield from bps.mv(*mv_args))
    else:
        yield from bps.null()


def open_shutters_wrapper(plan, registry: Registry | None = None):
    """Wrapper for Bluesky plans that opens and closes shutters as needed.

    Only shutters that are closed at the start of the plan are
    included.

    Shutters are split into two categories. **Fast shutters** (with
    the ophyd label ``"fast_shutters"``) will be **opened before a new
    detector trigger**, and closed after the trigger is awaited. All
    other shutters will be **opened at the start of the run**. Both
    categories will be closed at the end of the run.

    Parameters
    ==========
    plan
      The Bluesky plan instance to decorate.
    registry
      An ophyd-registry in which to look for shutters.

    """
    if registry is None:
        registry = beamline.devices
    # Get a list of shutters that could be opened and closed
    all_shutters = registry.findall(label="shutters", allow_none=True)
    all_shutters = [shtr for shtr in all_shutters if _can_open(shtr)]
    # Check for closed shutters (open shutters just stay open)
    shutters_to_open = []
    for shutter in all_shutters:
        initial_state = yield from bps.rd(shutter)
        if initial_state == ShutterState.CLOSED:
            shutters_to_open.append(shutter)
    # Organize the shutters into fast and slow
    fast_shutters = registry.findall(label="fast_shutters", allow_none=True)
    fast_shutters = [shtr for shtr in shutters_to_open if shtr in fast_shutters]
    slow_shutters = [shtr for shtr in shutters_to_open if shtr not in fast_shutters]
    # Open shutters
    yield from _set_shutters(slow_shutters, ShutterState.OPEN)
    # Add the wrapper for opening fast shutters at every trigger
    new_plan = open_fast_shutters_wrapper(plan, fast_shutters)
    # Add a wrapper to close all the shutters once the measurement is done
    close_shutters = _set_shutters(shutters_to_open, ShutterState.CLOSED)
    new_plan = finalize_wrapper(new_plan, close_shutters)
    # Execute the wrapped plan
    return_val = yield from new_plan
    return return_val


def open_fast_shutters_wrapper(plan, shutters):
    """Open and close each shutter when encountering a detector trigger."""
    response = None
    open_groups = set()
    while True:
        # Loop through the messages and get the next one in the queue
        try:
            msg = plan.send(response)
        except StopIteration as exc:
            return_val = exc.value
            break
        # Check for "trigger" messages to open shutters
        if msg.command == "trigger":
            if len(open_groups) == 0:
                yield from _set_shutters(shutters, ShutterState.OPEN)
            open_groups.add(msg.kwargs.get("group", None))
        # Emit the actual intended message
        response = yield msg
        # Check for "wait" messages to close shutters
        if msg.command == "wait":
            try:
                open_groups.remove(msg.kwargs.get("group", None))
            except KeyError:
                # Probably waiting on a group with no triggers
                pass
            else:
                if len(open_groups) == 0:
                    yield from _set_shutters(shutters, ShutterState.CLOSED)
    return return_val


open_shutters_decorator = make_decorator(open_shutters_wrapper)


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
