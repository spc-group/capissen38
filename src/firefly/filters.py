import json
from typing import Sequence

from pydm.widgets import PyDMEmbeddedDisplay

from firefly import display
from haven import beamline


class FiltersDisplay(display.FireflyDisplay):
    filters: Sequence

    def ui_filename(self):
        return "filters.ui"

    def customize_device(self):
        filters = beamline.devices.findall(label="filters", allow_none=True)
        self.filters = sorted(filters, key=lambda dev: dev.name)

    def customize_ui(self):
        # Delete existing filter widgets
        for idx in reversed(range(self.filters_layout.count())):
            self.filters_layout.takeAt(idx).widget().deleteLater()
        # Add embedded displays for all the ion chambers
        self._filter_displays = []
        for idx, device in enumerate(self.filters):
            # Create the display object
            disp = PyDMEmbeddedDisplay(parent=self)
            disp.macros = json.dumps({"DEV": device.name})
            disp.filename = "filters_row.ui"
            # Add the Embedded Display to the Results Layout
            self.filters_layout.addWidget(disp)
            self._filter_displays.append(disp)
