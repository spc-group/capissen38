import asyncio
import logging

from bluesky_queueserver_api import BPlan
from qasync import asyncSlot
from qtpy import QtWidgets
from qtpy.QtGui import QDoubleValidator

from firefly.component_selector import ComponentSelector
from firefly.plans import regions_display

log = logging.getLogger()


class LineScanRegion(regions_display.RegionBase):

    def setup_ui(self):
        self.layout = QtWidgets.QHBoxLayout()

        # First item, ComponentSelector
        self.motor_box = ComponentSelector()
        self.layout.addWidget(self.motor_box)

        # Second item, start point
        self.start_line_edit = QtWidgets.QLineEdit()
        self.start_line_edit.setValidator(QDoubleValidator())  # only takes floats
        self.start_line_edit.setPlaceholderText("Start…")
        self.layout.addWidget(self.start_line_edit)

        # Third item, stop point
        self.stop_line_edit = QtWidgets.QLineEdit()
        self.stop_line_edit.setValidator(QDoubleValidator())  # only takes floats
        self.stop_line_edit.setPlaceholderText("Stop…")
        self.layout.addWidget(self.stop_line_edit)


class LineScanDisplay(regions_display.RegionsDisplay):
    Region = LineScanRegion

    @asyncSlot(object)
    async def update_devices_slot(self, registry):
        await self.update_devices(registry)
        await self.detectors_list.update_devices(registry)

    def customize_ui(self):
        super().customize_ui()
        # When selections of detectors changed update_total_time
        self.ui.detectors_list.selectionModel().selectionChanged.connect(
            self.update_total_time
        )
        self.ui.spinBox_repeat_scan_num.valueChanged.connect(self.update_total_time)
        self.ui.scan_pts_spin_box.valueChanged.connect(self.update_total_time)
    

    def queue_plan(self, *args, **kwargs):
        """Execute this plan on the queueserver."""
        detectors, num_points, motor_args, repeat_scan_num, md = (
            self.get_scan_parameters()
        )

        if self.ui.relative_scan_checkbox.isChecked():
            if self.ui.log_scan_checkbox.isChecked():
                scan_type = "rel_log_scan"
            else:
                scan_type = "rel_scan"
        else:
            if self.ui.log_scan_checkbox.isChecked():
                scan_type = "log_scan"
            else:
                scan_type = "scan"

        # # Build the queue item
        item = BPlan(
            scan_type,
            detectors,
            *motor_args,
            num=num_points,
            # per_step=None,
            md=md,
        )

        # Submit the item to the queueserver
        log.info("Added line scan() plan to queue.")
        # repeat scans
        for i in range(repeat_scan_num):
            self.queue_item_submitted.emit(item)

    def ui_filename(self):
        return "plans/line_scan.ui"


# -----------------------------------------------------------------------------
# :author:    Juanjuan Huang
# :email:     juanjuan.huang@anl.gov
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
