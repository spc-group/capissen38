import logging

import numpy as np
from bluesky_queueserver_api import BPlan
from qasync import asyncSlot
from qtpy import QtWidgets
from qtpy.QtGui import QDoubleValidator

from firefly.component_selector import ComponentSelector
from firefly.plans import regions_display

log = logging.getLogger()


class TitleRegion:
    def __init__(self):
        self.setup_ui()

    def setup_ui(self):
        self.layout = QtWidgets.QGridLayout()
        labels = [
            "Priority axis",
            "Motor",
            "Start",
            "Stop",
            "N. points",
            "Size",
            "Snake",
            "Fly",
        ]
        Qlabels_all = {}

        # add labels in the first row
        for i, label_i in enumerate(labels):
            Qlabel_i = QtWidgets.QLabel(label_i)
            self.layout.addWidget(Qlabel_i, 0, i)
            Qlabels_all[label_i] = Qlabel_i

        # fix widths so the labels are aligned with GridScanRegions
        Qlabels_all["Priority axis"].setFixedWidth(70)
        Qlabels_all["Motor"].setFixedWidth(100)
        Qlabels_all["N. points"].setFixedWidth(68)
        Qlabels_all["Snake"].setFixedWidth(53)
        Qlabels_all["Fly"].setFixedWidth(43)

        # add labels in the second row
        label = QtWidgets.QLabel("fast -> slow")
        self.layout.addWidget(label, 1, 0)


class GridScanRegion(regions_display.RegionBase):

    def setup_ui(self):
        self.layout = QtWidgets.QHBoxLayout()

        # motor No.
        self.motor_label = QtWidgets.QLCDNumber()
        self.motor_label.setStyleSheet(
            "QLCDNumber { background-color: white; color: red; }"
        )
        self.motor_label.display(self.line_label)
        self.layout.addWidget(self.motor_label)

        # ComponentSelector
        self.motor_box = ComponentSelector()
        self.layout.addWidget(self.motor_box)

        # Start point
        self.start_line_edit = QtWidgets.QLineEdit()
        self.start_line_edit.setValidator(QDoubleValidator())  # only takes floats
        self.start_line_edit.setPlaceholderText("Start…")
        self.layout.addWidget(self.start_line_edit)

        # Stop point
        self.stop_line_edit = QtWidgets.QLineEdit()
        self.stop_line_edit.setValidator(QDoubleValidator())  # only takes floats
        self.stop_line_edit.setPlaceholderText("Stop…")
        self.layout.addWidget(self.stop_line_edit)

        # Number of scan point
        self.scan_pts_spin_box = QtWidgets.QSpinBox()
        self.scan_pts_spin_box.setMinimum(1)
        self.scan_pts_spin_box.setMaximum(99999)
        self.layout.addWidget(self.scan_pts_spin_box)

        # Step size (non-editable)
        self.step_size_line_edit = QtWidgets.QLineEdit()
        self.step_size_line_edit.setReadOnly(True)
        self.step_size_line_edit.setDisabled(True)
        self.step_size_line_edit.setPlaceholderText("Step Size…")
        self.layout.addWidget(self.step_size_line_edit)

        # Snake checkbox
        self.snake_checkbox = QtWidgets.QCheckBox()
        self.snake_checkbox.setText("Snake")
        self.snake_checkbox.setEnabled(True)
        self.layout.addWidget(self.snake_checkbox)

        # Fly checkbox # not available right now
        self.fly_checkbox = QtWidgets.QCheckBox()
        self.fly_checkbox.setText("Fly")
        self.fly_checkbox.setEnabled(False)
        self.layout.addWidget(self.fly_checkbox)

        # Connect signals
        self.start_line_edit.textChanged.connect(self.update_step_size)
        self.stop_line_edit.textChanged.connect(self.update_step_size)
        self.scan_pts_spin_box.valueChanged.connect(self.update_step_size)

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

            # Ensure num_points is an integer
            num_points = int(self.scan_pts_spin_box.value())  # Corrected method call

            # Calculate step size
            if num_points > 1:
                step_size = (stop - start) / (num_points - 1)
                self.step_size_line_edit.setText(f"{step_size:.5g}")
            else:
                self.step_size_line_edit.setText("N/A")
        except ValueError:
            self.step_size_line_edit.setText("N/A")


class GridScanDisplay(regions_display.RegionsDisplay):
    Region = GridScanRegion
    default_num_regions = 2

    def __init__(self, parent=None, args=None, macros=None, ui_filename=None, **kwargs):
        super().__init__(parent, args, macros, ui_filename, **kwargs)

    def customize_ui(self):
        super().customize_ui()
        self.update_snakes()
        # add title layout
        self.title_region = TitleRegion()
        self.ui.title_layout.addLayout(self.title_region.layout)
        # Connect scan points change to update total time
        for region in self.regions:
            region.scan_pts_spin_box.valueChanged.connect(self.update_total_time)

    def time_per_scan(self, detector_time):
        total_num_pnts = np.prod(
            [region_i.scan_pts_spin_box.value() for region_i in self.regions]
        )
        total_time_per_scan = total_num_pnts * detector_time
        return total_time_per_scan

    @asyncSlot(object)
    async def update_devices_slot(self, registry):
        await super().update_devices(registry)
        await self.detectors_list.update_devices(registry)

    @asyncSlot(int)
    async def update_regions_slot(self, new_region_num: int):
        await super().update_regions(new_region_num)
        self.update_snakes()

    def update_snakes(self):
        """Update the snake checkboxes.

        The last region is not snakable, so that checkbox gets
        disabled and unchecked. The rest get enabled.

        """
        if len(self.regions) > 0:
            self.regions[-1].snake_checkbox.setEnabled(False)
            self.regions[-1].snake_checkbox.setChecked(False)
            for region_i in self.regions[:-1]:
                region_i.snake_checkbox.setEnabled(True)

    def get_scan_parameters(self):
        # Get scan parameters from widgets
        detectors = self.ui.detectors_list.selected_detectors()
        repeat_scan_num = int(self.ui.spinBox_repeat_scan_num.value())

        # Get paramters from each rows of line regions:
        motor_lst, start_lst, stop_lst, num_points_lst = [], [], [], []
        for region_i in reversed(self.regions):
            motor_lst.append(region_i.motor_box.current_component().name)
            start_lst.append(float(region_i.start_line_edit.text()))
            stop_lst.append(float(region_i.stop_line_edit.text()))
            num_points_lst.append(int(region_i.scan_pts_spin_box.value()))

        motor_args = [
            values
            for motor_i in zip(motor_lst, start_lst, stop_lst, num_points_lst)
            for values in motor_i
        ]

        return detectors, motor_args, repeat_scan_num

    def queue_plan(self, *args, **kwargs):
        """Execute this plan on the queueserver."""
        detectors, motor_args, repeat_scan_num = self.get_scan_parameters()
        md = self.get_meta_data()

        # get snake axes, if all unchecked, set it None
        snake_axes = [
            region_i.motor_box.current_component().name
            for i, region_i in enumerate(self.regions)
            if region_i.snake_checkbox.isChecked()
        ]

        if snake_axes == []:
            snake_axes = False

        if self.ui.relative_scan_checkbox.isChecked():
            scan_type = "rel_grid_scan"
        else:
            scan_type = "grid_scan"

        # Build the queue item
        item = BPlan(
            scan_type,
            detectors,
            *motor_args,
            snake_axes=snake_axes,
            md=md,
        )

        # Submit the item to the queueserver
        log.info(f"Added grid_scan() plan to queue ({repeat_scan_num} scans).")
        # repeat scans
        for i in range(repeat_scan_num):
            self.queue_item_submitted.emit(item)

    def ui_filename(self):
        return "plans/grid_scan.ui"


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
