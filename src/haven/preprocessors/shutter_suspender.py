import logging

from bluesky.preprocessors import finalize_wrapper

# from bluesky.suspenders import SuspendBoolLow
from bluesky.utils import Msg, make_decorator

from haven.instrument import beamline

log = logging.getLogger()


def shutter_suspend_wrapper(plan, shutter_signals=None):
    """
    Install suspenders to the RunEngine, and remove them at the end.

    Parameters
    ----------
    plan : iterable or iterator
        a generator, list, or similar containing `Msg` objects
    suspenders : suspender or list of suspenders
        Suspenders to use for the duration of the wrapper

    Yields
    ------
    msg : Msg
        messages from plan, with 'install_suspender' and 'remove_suspender'
        messages inserted and appended
    """
    if shutter_signals is None:
        shutters = beamline.devices.findall("shutters", allow_none=True)
        shutter_signals = [s.pss_state for s in shutters]
    # Create a suspender for each shutter
    suspenders = []

    ###################################################
    # Temporarily disabled for technical commissioning
    ###################################################
    # for sig in shutter_signals:
    #     suspender = SuspendBoolLow(sig, sleep=3.0)
    #     suspenders.append(suspender)
    # if not isinstance(suspenders, Iterable):
    #     suspenders = [suspenders]

    def _install():
        for susp in suspenders:
            yield Msg("install_suspender", None, susp)

    def _remove():
        for susp in suspenders:
            yield Msg("remove_suspender", None, susp)

    def _inner_plan():
        yield from _install()
        return (yield from plan)

    return (yield from finalize_wrapper(_inner_plan(), _remove()))


shutter_suspend_decorator = make_decorator(shutter_suspend_wrapper)


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
