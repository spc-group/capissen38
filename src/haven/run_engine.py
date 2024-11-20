import logging

import databroker
import IPython
from bluesky import RunEngine as BlueskyRunEngine
from bluesky.callbacks.best_effort import BestEffortCallback
from bluesky.utils import ProgressBarManager, register_transform

from .exceptions import ComponentNotFound
from .instrument import beamline
from .preprocessors import inject_haven_md_wrapper
from .xdi_export import XDIWriter

log = logging.getLogger(__name__)


catalog = None


def save_data(name, doc):
    # This is a hack around a problem with garbage collection
    # Has been fixed in main, maybe released in databroker v2?
    # Create the databroker callback if necessary
    global catalog
    if catalog is None:
        catalog = databroker.catalog["bluesky"]
    # Save the document
    catalog.v1.insert(name, doc)


def run_engine(connect_databroker=True, use_bec=True, **kwargs) -> BlueskyRunEngine:
    RE = BlueskyRunEngine(**kwargs)
    # Add the best-effort callback
    if use_bec:
        RE.subscribe(BestEffortCallback())
    # Install suspenders
    try:
        aps = beamline.registry.find("APS")
    except ComponentNotFound:
        log.warning("APS device not found, suspenders not installed.")
    else:
        # Suspend when shutter permit is disabled
        # Re-enable when the APS shutter permit signal is better understood
        pass
        # RE.install_suspender(
        #     suspenders.SuspendWhenChanged(
        #         signal=aps.shutter_permit,
        #         expected_value="PERMIT",
        #         allow_resume=True,
        #         sleep=3,
        #         tripped_message="Shutter permit revoked.",
        #     )
        # )
    # Add a shortcut for using the run engine more efficiently
    RE.waiting_hook = ProgressBarManager()
    if (ip := IPython.get_ipython()) is not None:
        register_transform("RE", prefix="<", ip=ip)
    # Install databroker connection
    if connect_databroker:
        RE.subscribe(save_data)
    # Add preprocessors
    RE.preprocessors.append(inject_haven_md_wrapper)
    return RE


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
