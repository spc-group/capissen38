import logging

from ophyd import Device, EpicsMotor
from ophyd import FormattedComponent as FCpt

from .._iconfig import load_config
from .device import make_device

__all__ = ["XYStage", "load_stages"]


log = logging.getLogger(__name__)


class XYStage(Device):
    """An XY stage with two motors operating in orthogonal directions.

    Vertical and horizontal are somewhat arbitrary, but are expected
    to align with the orientation of a camera monitoring the stage.

    Parameters
    ==========

    pv_vert
      The suffix to the PV for the vertical motor.
    pv_horiz
      The suffix to the PV for the horizontal motor.
    """

    vert = FCpt(EpicsMotor, "{prefix}{pv_vert}", labels={"motors"})
    horiz = FCpt(EpicsMotor, "{prefix}{pv_horiz}", labels={"motors"})

    def __init__(
        self,
        prefix: str,
        pv_vert: str,
        pv_horiz: str,
        labels={"stages"},
        *args,
        **kwargs,
    ):
        self.pv_vert = pv_vert
        self.pv_horiz = pv_horiz
        super().__init__(prefix, labels=labels, *args, **kwargs)


def load_stages(config=None):
    """Load the stages defined in the configuration files' ``[stage]``
    sections.

    """
    if config is None:
        config = load_config()
    devices = []
    for name, stage_data in config.get("stage", {}).items():
        devices.append(
            make_device(
                XYStage,
                name=name,
                prefix=stage_data["prefix"],
                pv_vert=stage_data["pv_vert"],
                pv_horiz=stage_data["pv_horiz"],
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
