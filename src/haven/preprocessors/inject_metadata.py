import getpass
import logging
import os
import socket
import warnings
from collections import ChainMap

import epics
import pkg_resources
from bluesky.preprocessors import msg_mutator

from haven import __version__ as haven_version
from haven._iconfig import load_config
from haven.exceptions import ComponentNotFound
from haven.instrument import beamline

log = logging.getLogger()


def get_version(pkg_name):
    return pkg_resources.get_distribution(pkg_name).version


VERSIONS = dict(
    apstools=get_version("apstools"),
    bluesky=get_version("bluesky"),
    databroker=get_version("databroker"),
    epics_ca=epics.__version__,
    epics=epics.__version__,
    haven=haven_version,
    h5py=get_version("h5py"),
    matplotlib=get_version("matplotlib"),
    numpy=get_version("numpy"),
    ophyd=get_version("ophyd"),
    pymongo=get_version("pymongo"),
)


def inject_haven_md_wrapper(plan):
    """Inject additional metadata into a run.

    This takes precedences over the original metadata dict in the event of
    overlapping keys, but it does not mutate the original metadata dict.
    (It uses ChainMap.)

    Parameters
    ----------
    plan : iterable or iterator
        a generator, list, or similar containing `Msg` objects

    """

    def _inject_md(msg):
        if msg.command != "open_run":
            return msg
        # Prepare the metadata dictionary
        config = load_config()
        md = {
            # Software versions
            "versions": VERSIONS,
            # Controls
            "EPICS_HOST_ARCH": os.environ.get("EPICS_HOST_ARCH"),
            "epics_libca": os.environ.get("PYEPICS_LIBCA"),
            "EPICS_CA_MAX_ARRAY_BYTES": os.environ.get("EPICS_CA_MAX_ARRAY_BYTES"),
            # Facility
            "beamline_id": config["beamline"]["name"],
            "facility_id": ", ".join(cfg["name"] for cfg in config["synchrotron"]),
            "xray_source": config["xray_source"]["type"],
            # Computer
            "login_id": f"{getpass.getuser()}@{socket.gethostname()}",
            "pid": os.getpid(),
            # User supplied
            "sample_name": "",
            # Bluesky
            "parameters": "",
            "purpose": "",
        }
        # Get metadata from the beamline scheduling system (bss)
        try:
            bss = beamline.devices["bss"]
        except ComponentNotFound:
            wmsg = "Could not find bss device, metadata may be missing."
            warnings.warn(wmsg)
            log.warning(wmsg)
            bss_md = None
        else:
            bss_md = bss.get()
            md.update(
                {
                    "proposal_id": bss_md.proposal.proposal_id,
                    "proposal_title": bss_md.proposal.title,
                    "proposal_users": bss_md.proposal.user_last_names,
                    "proposal_user_badges": bss_md.proposal.user_badges,
                    "esaf_id": bss_md.esaf.esaf_id,
                    "esaf_title": bss_md.esaf.title,
                    "esaf_users": bss_md.esaf.user_last_names,
                    "esaf_user_badges": bss_md.esaf.user_badges,
                    "mail_in_flag": bss_md.proposal.mail_in_flag,
                    "proprietary_flag": bss_md.proposal.proprietary_flag,
                    "bss_aps_cycle": bss_md.esaf.aps_cycle,
                    "bss_beamline_name": bss_md.proposal.beamline_name,
                }
            )
        # Update the message
        msg = msg._replace(kwargs=ChainMap(msg.kwargs, md))
        return msg

    return (yield from msg_mutator(plan, _inject_md))


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
