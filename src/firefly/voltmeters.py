import logging
from functools import partial
from typing import Sequence

import qtawesome as qta
from bluesky_queueserver_api import BPlan
from pydm.widgets import PyDMChannel, PyDMLabel, PyDMPushButton
from pydm.widgets.analog_indicator import PyDMAnalogIndicator
from pydm.widgets.display_format import DisplayFormat
from qasync import asyncSlot
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
)

import haven
from firefly import display

log = logging.getLogger(__name__)


class VoltmetersDisplay(display.FireflyDisplay):
    _ion_chamber_rows: Sequence

    # Signals
    details_window_requested = Signal(str)  # ion-chamber device name

    def customize_ui(self):
        # Connect support for running the auto_gain and dark current plans
        self.ui.auto_gain_button.setToolTip(haven.plans.auto_gain.__doc__)
        self.ui.auto_gain_button.clicked.connect(self.run_auto_gain)
        self.ui.dark_current_button.clicked.connect(self.record_dark_current)
        # Adjust layouts
        self.ui.voltmeters_layout.setHorizontalSpacing(0)
        self.ui.voltmeters_layout.setVerticalSpacing(0)

    def clear_layout(self, layout):
        if layout is None:
            return
        while layout.count() > 0:
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            else:
                self.clear_layout(item.layout())

    @asyncSlot(object)
    async def update_devices(self, registry):
        ion_chambers = registry.findall(label="ion_chambers")
        self.ion_chambers = sorted(
            ion_chambers, key=lambda c: c.scaler_channel.raw_count.source
        )
        # Clear the voltmeters grid layout
        self.clear_layout(self.voltmeters_layout)
        # Add embedded displays for all the ion chambers
        self._ion_chamber_rows = []
        for row_idx, ic in enumerate(self.ion_chambers):
            # Create the display object
            row = Row(number=row_idx, ion_chamber=ic)
            self._ion_chamber_rows.append(row)
            # Add widgets to the grid layout
            for col_idx, layout in enumerate(row.column_layouts):
                self.ui.voltmeters_layout.addLayout(layout, row_idx, col_idx)
            # Connect the details button signal
            details_slot = partial(self.details_window_requested.emit, ic.name)
            row.details_button.clicked.connect(details_slot)
        # Remove old shutters from the combobox
        for idx in range(self.ui.shutter_combobox.count()):
            self.ui.shutter_combobox.removeItem(idx)

        # Decide which shutters we should show (only those that can be opened/closed)
        def is_controllable(shtr):
            can_open = getattr(shtr, "allow_open", True)
            can_close = getattr(shtr, "allow_close", True)
            return can_open and can_close

        shutters = registry.findall("shutters", allow_none=True)
        shutters = [shtr for shtr in shutters if is_controllable(shtr)]
        has_shutters = bool(len(shutters))
        # Add the shutters to the shutter combobox
        if has_shutters:
            self.ui.shutter_checkbox.setEnabled(True)
            for shutter in shutters:
                self.ui.shutter_combobox.addItem(shutter.name)
        else:
            log.warning("No shutters found, disabling checkbox.")
            self.ui.shutter_checkbox.setEnabled(False)
            self.ui.shutter_checkbox.setCheckState(False)

    def update_queue_status(self, status):
        super().update_queue_status(status)
        # Update widgets when the queue status changes
        self.ui.auto_gain_button.update_queue_style(status)
        self.ui.dark_current_button.update_queue_style(status)

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
        for row in self._ion_chamber_rows:
            if row.auto_gain_checkbox.isChecked():
                ic_names.append(row.device.name)
        # Construct the plan
        item = BPlan("auto_gain", ic_names, **kw)
        # Send it to the queue server
        self.queue_item_submitted.emit(item)

    def record_dark_current(self):
        """Add an item to queueserver to record the dark current of the ion
        chambers.

        """
        # Determine which shutters to close
        kwargs = {}
        if self.ui.shutter_checkbox.isChecked():
            shutter_name = self.ui.shutter_combobox.currentText()
            kwargs["shutters"] = [shutter_name]
        # Construct the plan
        ic_names = [ic.name for ic in self.ion_chambers]
        item = BPlan("record_dark_current", ic_names, **kwargs)
        # Send it to the queue server
        self.queue_item_submitted.emit(item)

    def ui_filename(self):
        return "voltmeters.ui"


class Row:
    """An row in the voltmeters display for a single ion chamber's signal."""

    def __init__(self, parent=None, *args, number: int, ion_chamber):
        self.parent = parent
        self.number = number
        self.device = ion_chamber
        self.setup_ui()

    def setup_ui(self):
        # Create container layouts for each column
        num_columns = 5
        self.column_layouts = []
        for idx in range(num_columns):
            layout = QVBoxLayout()
            self.column_layouts.append(layout)
        ##################
        # Create widgets #
        ##################
        device_name = self.device.name
        # Description label
        self.name_label = PyDMLabel(
            parent=self.parent,
            init_channel=f"haven://{device_name}.scaler_channel.description",
        )
        self.name_label.setStyleSheet('font: 12pt "Sans Serif";\nfont-weight: bold;')
        self.column_layouts[0].addWidget(self.name_label)
        # Analog indicator
        self.voltage_indicator = PyDMAnalogIndicator(
            parent=self.parent,
            init_channel=f"haven://{device_name}.voltmeter_channel.final_value",
        )
        self.voltage_indicator.showValue = False
        self.voltage_indicator.limitsFromChannel = False
        self.voltage_indicator.minorAlarmFromChannel = False
        self.voltage_indicator.majorAlarmFromChannel = False
        self.voltage_indicator.userLowerLimit = 0.0
        self.voltage_indicator.userUpperLimit = 5.0
        self.voltage_indicator.userUpperMinorAlarm = 4.5
        self.voltage_indicator.userLowerMinorAlarm = 0.5
        self.voltage_indicator.userUpperMajorAlarm = 5.0
        self.voltage_indicator.userLowerMajorAlarm = 0.15
        self.column_layouts[1].addWidget(self.voltage_indicator)
        # Voltage labels
        self.column_layouts[2].addItem(VSpacer())
        self.voltage_label_layout = QHBoxLayout()
        self.voltage_label_layout.setSpacing(3)
        self.column_layouts[2].addLayout(self.voltage_label_layout)
        self.voltage_label_layout.addItem(HSpacer())
        self.voltage_label = PyDMLabel(
            parent=self.parent,
            init_channel=f"haven://{device_name}.voltmeter_channel.final_value",
        )
        self.voltage_label.setStyleSheet('font: 12pt "Sans Serif";\nfont-weight: bold;')
        self.voltage_label_layout.addWidget(self.voltage_label)
        self.voltage_unit_label = QLabel(parent=self.parent)
        self.voltage_unit_label.setStyleSheet(
            'font: 12pt "Sans Serif";\nfont-weight: bold;'
        )
        self.voltage_unit_label.setText("V")
        self.voltage_label_layout.addWidget(self.voltage_unit_label)
        self.voltage_label_layout.addItem(HSpacer())
        # Current labels
        self.current_label_layout = QHBoxLayout()
        self.current_label_layout.setSpacing(3)
        self.column_layouts[2].addLayout(self.current_label_layout)
        self.current_label_layout.addItem(HSpacer())
        self.current_label = PyDMLabel(
            parent=self.parent,
            init_channel=f"haven://{device_name}.net_current",
        )
        self.current_label.displayFormat = DisplayFormat.Exponential
        self.current_label_layout.addWidget(self.current_label)
        self.current_unit_label = QLabel(parent=self.parent)
        self.current_unit_label.setText("A")
        self.current_label_layout.addWidget(self.current_unit_label)
        self.current_label_layout.addItem(HSpacer())
        self.column_layouts[2].addItem(VSpacer())
        # Label for the gain/offset column header
        self.column_layouts[3].addItem(VSpacer())
        self.gain_header_label = QLabel()
        self.gain_header_label.setText("Gain/Offset")
        self.gain_header_label.setAlignment(Qt.AlignCenter)
        self.column_layouts[3].addWidget(self.gain_header_label)
        # Gain up/down buttons
        self.gain_buttons_layout = QHBoxLayout()
        self.column_layouts[3].addLayout(self.gain_buttons_layout)
        self.gain_buttons_layout.addItem(HSpacer())
        self.gain_down_button = PyDMPushButton(
            init_channel=f"haven://{device_name}.preamp.gain_level",
            relative=True,
            pressValue=-1,
            icon=qta.icon("fa5s.arrow-left"),
        )
        self.gain_buttons_layout.addWidget(self.gain_down_button)
        self.gain_up_button = PyDMPushButton(
            init_channel=f"haven://{device_name}.preamp.gain_level",
            relative=True,
            pressValue=1,
            icon=qta.icon("fa5s.arrow-right"),
        )
        self.gain_buttons_layout.addWidget(self.gain_up_button)
        self.gain_buttons_layout.addItem(HSpacer())
        self.gain_monitor = PyDMChannel(
            address=f"haven://{device_name}.preamp.gain_level",
            value_slot=self.update_gain_level_widgets,
        )
        self.gain_monitor.connect()
        # Reporting the current gain as text
        self.gain_label_layout = QHBoxLayout()
        self.column_layouts[3].addLayout(self.gain_label_layout)
        self.gain_label_layout.addItem(HSpacer())
        self.gain_value_label = PyDMLabel(
            parent=self.parent,
            init_channel=f"haven://{device_name}.preamp.sensitivity_value",
        )
        self.gain_label_layout.addWidget(self.gain_value_label)
        self.gain_unit_label = PyDMLabel(
            parent=self.parent,
            init_channel=f"haven://{device_name}.preamp.sensitivity_unit",
        )
        self.gain_label_layout.addWidget(self.gain_unit_label)
        self.gain_label_layout.addItem(HSpacer())
        # Auto-gain and detail window controls
        self.column_layouts[4].addItem(VSpacer())
        self.auto_gain_checkbox = QCheckBox(parent=self.parent)
        self.auto_gain_checkbox.setText("Auto-gain")
        self.column_layouts[4].addWidget(self.auto_gain_checkbox)
        self.details_button = QPushButton(parent=self.parent)
        self.details_button.setText("More")
        self.details_button.setIcon(qta.icon("fa5s.cog"))
        self.details_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)
        self.column_layouts[4].addWidget(self.details_button)
        self.column_layouts[4].addItem(VSpacer())

    def update_gain_level_widgets(self, new_level):
        if new_level == 0:
            can_go_down, can_go_up = (False, True)
        elif new_level == 27:
            can_go_down, can_go_up = (True, False)
        else:
            can_go_down, can_go_up = (True, True)
        self.gain_down_button.setEnabled(can_go_down)
        self.gain_up_button.setEnabled(can_go_up)


class VSpacer(QSpacerItem):
    def __init__(
        self, w=40, h=20, hData=QSizePolicy.Expanding, vData=QSizePolicy.Minimum
    ):
        super().__init__(w, h, hData, vData)


class HSpacer(QSpacerItem):
    def __init__(
        self, w=40, h=20, hData=QSizePolicy.Expanding, vData=QSizePolicy.Minimum
    ):
        super().__init__(w, h, hData, vData)


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
