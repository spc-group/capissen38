import logging

from bluesky_queueserver_api import BPlan
from qasync import asyncSlot
from qtpy import QtWidgets
from qtpy.QtGui import QDoubleValidator

from firefly.component_selector import ComponentSelector
from firefly.plans import regions_display

log = logging.getLogger()


class LineScanRegion(regions_display.RegionBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.num_points = 2  # Default value for num_points

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

        # Step size (non-editable)
        self.step_size_line_edit = QtWidgets.QLineEdit()
        self.step_size_line_edit.setReadOnly(True)
        self.step_size_line_edit.setDisabled(True)
        self.step_size_line_edit.setPlaceholderText("Step Size…")
        self.layout.addWidget(self.step_size_line_edit)

        # Connect signals
        self.start_line_edit.textChanged.connect(self.update_step_size)
        self.stop_line_edit.textChanged.connect(self.update_step_size)

    def set_num_points(self, num_points):
        self.num_points = max(2, int(num_points))  # Ensure num_points is >= 2
        self.update_step_size()

    def update_step_size(self):
        try:
            # Get Start and Stop values
            start_text = self.start_line_edit.text().strip()
            stop_text = self.stop_line_edit.text().strip()
            if not start_text or not stop_text:
                self.step_size_line_edit.setText("N/A")
                return

            start = float(start_text)
            stop = float(stop_text)

            # Calculate step size
            if self.num_points > 1:
                step_size = (stop - start) / (self.num_points - 1)
                self.step_size_line_edit.setText(f"{step_size:.5g}")
            else:
                self.step_size_line_edit.setText("N/A")
        except ValueError:
            self.step_size_line_edit.setText("N/A")


class LineScanDisplay(regions_display.RegionsDisplay):
    Region = LineScanRegion

    @asyncSlot(object)
    async def update_devices_slot(self, registry):
        await self.update_devices(registry)
        await self.detectors_list.update_devices(registry)

    def time_per_scan(self, detector_time):
        num_points = self.ui.scan_pts_spin_box.value()
        total_time_per_scan = detector_time * num_points
        return total_time_per_scan

    def customize_ui(self):
        super().customize_ui()

        # Connect signals for total time updates
        self.ui.scan_pts_spin_box.valueChanged.connect(self.update_total_time)
        self.ui.detectors_list.selectionModel().selectionChanged.connect(
            self.update_total_time
        )

        for region in self.regions:
            self.ui.scan_pts_spin_box.valueChanged.connect(region.set_num_points)

    def update_regions_step_size(self, num_points):
        """Update the step size for all regions."""
        for region in self.regions:
            region.set_num_points(num_points)

    def queue_plan(self, *args, **kwargs):
        """Execute this plan on the queueserver."""
        detectors, motor_args, repeat_scan_num = self.get_scan_parameters()
        md = self.get_meta_data()
        num_points = self.ui.scan_pts_spin_box.value()
        # Check for what kind of scan we're running based on use input
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
        # Build the queue item
        item = BPlan(
            scan_type,
            detectors,
            *motor_args,
            num=num_points,
            md=md,
        )

        # Submit the item to the queueserver
        log.info(f"Adding line scan() plan to queue: {item}.")
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
