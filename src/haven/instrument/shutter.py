import logging

from apstools.devices.shutters import ApsPssShutterWithStatus as Shutter

from .._iconfig import load_config
from .device import make_device

log = logging.getLogger(__name__)


def load_shutters(config=None):
    if config is None:
        config = load_config()
    # Guard to make sure there's at least one shutter configuration
    if "shutter" not in config.keys():
        return []
    # Load the shutter configurations into devices
    prefix = config["shutter"]["prefix"]
    devices = []
    for name, d in config["shutter"].items():
        if name == "prefix":
            continue
        # Calculate suitable PV values
        hutch = d["hutch"]
        acronym = "FES" if hutch == "A" else f"S{hutch}S"
        devices.append(
            make_device(
                Shutter,
                prefix=f"{prefix}:{acronym}",
                open_pv=f"{prefix}:{acronym}_OPEN_EPICS.VAL",
                close_pv=f"{prefix}:{acronym}_CLOSE_EPICS.VAL",
                state_pv=f"{prefix}:{hutch}_BEAM_PRESENT",
                name=name,
                labels={"shutters"},
            )
        )
    return devices


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
