import json
import logging
from typing import Mapping, Optional, Sequence

from bluesky_queueserver_api import BPlan
from pydm.widgets import PyDMEmbeddedDisplay
from qtpy import QtWidgets

import haven
from firefly import FireflyApplication, display

# from .voltmeter import VoltmeterDisplay


log = logging.getLogger(__name__)


class VoltmetersDisplay(display.FireflyDisplay):
    _ion_chamber_displays = []
    caqtdm_scaler_ui_file: str = "/net/s25data/xorApps/ui/scaler32_full_offset.ui"
    caqtdm_mcs_ui_file: str = (
        "/APSshare/epics/synApps_6_2_1/support/mca-R7-9//mcaApp/op/ui/autoconvert/SIS38XX.ui"
    )

    def __init__(
        self,
        args: Optional[Sequence] = None,
        macros: Mapping = {},
        **kwargs,
    ):
        ion_chambers = haven.registry.findall(label="ion_chambers", allow_none=True)
        self.ion_chambers = sorted(ion_chambers, key=lambda c: c.ch_num)
        macros_ = macros.copy()
        if "SCALER" not in macros_.keys():
            macros_["SCALER"] = self.ion_chambers[0].scaler_prefix
        super().__init__(args=args, macros=macros_, **kwargs)

    def customize_ui(self):
        # Delete existing voltmeter widgets
        for idx in reversed(range(self.voltmeters_layout.count())):
            self.voltmeters_layout.takeAt(idx).widget().deleteLater()
        # Add embedded displays for all the ion chambers
        self._ion_chamber_displays = []
        for idx, ic in enumerate(self.ion_chambers):
            # Add a separator
            if idx > 0:
                line = QtWidgets.QFrame(self.ui)
                line.setObjectName("line")
                # line->setGeometry(QRect(140, 80, 118, 3));
                line.setFrameShape(QtWidgets.QFrame.HLine)
                line.setFrameShadow(QtWidgets.QFrame.Sunken)
                self.voltmeters_layout.addWidget(line)
            # Create the display object
            disp = PyDMEmbeddedDisplay(parent=self)
            disp.macros = json.dumps({"IC": ic.name})
            disp.filename = "voltmeter.py"
            # Add the Embedded Display to the Results Layout
            self.voltmeters_layout.addWidget(disp)
            self._ion_chamber_displays.append(disp)
        # Connect support for running the auto_gain plan
        self.ui.auto_gain_button.setToolTip(haven.auto_gain.__doc__)
        self.ui.auto_gain_button.clicked.connect(self.run_auto_gain)

    def run_auto_gain(self):
        """Send a plan to the queueserver to auto-gain the pre-amps."""
        # Get plan arguments from display widgets
        kw = {}
        volts_min = self.ui.volts_min_line_edit.text()
        if volts_min != "":
            kw["volts_min"] = float(volts_min)
        volts_max = self.ui.volts_max_line_edit.text()
        if volts_max != "":
            kw["volts_max"] = float(volts_max)
        # Check which ion chambers to run the plan with
        ic_names = []
        for ic_disp in self._ion_chamber_displays:
            if ic_disp.embedded_widget is None:
                continue
            if ic_disp.embedded_widget.ui.auto_gain_checkbox.isChecked():
                ic_names.append(ic_disp.embedded_widget.macros()["IC"])
        # Construct the plan
        item = BPlan("auto_gain", ic_names, **kw)
        # Send it to the queue server
        app = FireflyApplication.instance()
        app.add_queue_item(item)

    def ui_filename(self):
        return "voltmeters.ui"


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
