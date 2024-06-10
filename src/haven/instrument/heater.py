import logging

from apstools.devices import PTC10AioChannel as PTC10AioChannelBase
from apstools.devices import PTC10PositionerMixin, PTC10TcChannel
from ophyd import Component as Cpt
from ophyd import EpicsSignal, EpicsSignalRO, EpicsSignalWithRBV, PVPositioner

from .._iconfig import load_config
from .device import make_device

log = logging.getLogger(__name__)


# The apstools version uses "voltage_RBV" as the PVname
class PTC10AioChannel(PTC10AioChannelBase):
    """
    SRS PTC10 AIO module
    """

    voltage = Cpt(EpicsSignalRO, "output_RBV", kind="normal")


class CapillaryHeater(PTC10PositionerMixin, PVPositioner):
    readback = Cpt(EpicsSignalRO, "2A:temperature", kind="hinted")
    setpoint = Cpt(EpicsSignalWithRBV, "5A:setPoint", kind="hinted")

    # Additional modules installed on the PTC10
    pid = Cpt(PTC10AioChannel, "5A:")
    tc = Cpt(PTC10TcChannel, "2A:")
    output_enable = Cpt(EpicsSignal, "outputEnable", kind="omitted")


def load_heaters(config=None):
    if config is None:
        config = load_config()
    # Load the heaters
    devices = []
    for name, cfg in config.get("heater", {}).items():
        Cls = globals().get(cfg["device_class"])
        devices.append(
            make_device(Cls, prefix=f"{cfg['prefix']}:", name=name, labels={"heaters"})
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
