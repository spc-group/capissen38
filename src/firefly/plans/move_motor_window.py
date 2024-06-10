import logging

from bluesky_queueserver_api import BPlan
from qtpy import QtWidgets
from qtpy.QtGui import QDoubleValidator

from firefly import display
from firefly.application import FireflyApplication
from firefly.component_selector import ComponentSelector

log = logging.getLogger()


class MotorRegion:
    def __init__(self):
        self.setup_ui()

    def setup_ui(self):
        self.layout = QtWidgets.QHBoxLayout()

        # First item, ComponentSelector
        self.motor_box = ComponentSelector()
        self.layout.addWidget(self.motor_box)

        # Second item, position point
        self.position_line_edit = QtWidgets.QLineEdit()
        self.position_line_edit.setValidator(QDoubleValidator())  # only takes floats
        self.position_line_edit.setPlaceholderText("Position…")
        self.layout.addWidget(self.position_line_edit)


class MoveMotorDisplay(display.FireflyDisplay):
    default_num_regions = 1

    def customize_ui(self):
        # Remove the default layout from .ui file
        self.clearLayout(self.ui.region_template_layout)
        self.reset_default_regions()

        # disable the line edits in spin box
        self.ui.num_motor_spin_box.lineEdit().setReadOnly(True)
        self.ui.num_motor_spin_box.valueChanged.connect(self.update_regions)

        self.ui.run_button.setEnabled(True)  # for testing
        self.ui.run_button.clicked.connect(self.queue_plan)

    def time_converter(self, total_seconds):
        hours = round(total_seconds // 3600)
        minutes = round((total_seconds % 3600) // 60)
        seconds = round(total_seconds % 60)
        if total_seconds == -1:
            hours, minutes, seconds = "N/A", "N/A", "N/A"
        return hours, minutes, seconds

    def clearLayout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

    def reset_default_regions(self):
        if not hasattr(self, "regions"):
            self.regions = []
            self.add_regions(self.default_num_regions)
        self.ui.num_motor_spin_box.setValue(self.default_num_regions)
        self.update_regions()

    def add_regions(self, num=1):
        for i in range(num):
            region = MotorRegion()
            self.ui.regions_layout.addLayout(region.layout)
            # Save it to the list
            self.regions.append(region)

    def remove_regions(self, num=1):
        for i in range(num):
            layout = self.regions[-1].layout
            # iterate/wait, and delete all widgets in the layout in the end
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self.regions.pop()

    def update_regions(self):
        new_region_num = self.ui.num_motor_spin_box.value()
        old_region_num = len(self.regions)
        diff_region_num = new_region_num - old_region_num

        if diff_region_num < 0:
            self.remove_regions(abs(diff_region_num))
        elif diff_region_num > 0:
            self.add_regions(diff_region_num)

    def get_scan_parameters(self):
        # get paramters from each rows of line regions:
        motor_lst, position_lst = [], []
        for region_i in self.regions:
            motor_lst.append(region_i.motor_box.current_component().name)
            position_lst.append(float(region_i.position_line_edit.text()))

        motor_args = [
            values for motor_i in zip(motor_lst, position_lst) for values in motor_i
        ]

        # get meta data info
        md = {
            "sample": self.ui.lineEdit_sample.text(),
            "purpose": self.ui.lineEdit_purpose.text(),
        }

        return motor_args, md

    def queue_plan(self, *args, **kwargs):
        """Execute this plan on the queueserver."""
        motor_args, md = self.get_scan_parameters()

        if self.ui.relative_scan_checkbox.isChecked():
            scan_type = "mvr"
        else:
            scan_type = "mv"

        # # Build the queue item
        item = BPlan(
            scan_type,
            *motor_args,
            md=md,
        )

        # Submit the item to the queueserver
        app = FireflyApplication.instance()
        log.info("Added line scan() plan to queue.")
        app.add_queue_item(item)

    def ui_filename(self):
        return "plans/move_motor_window.ui"


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
