import json

from pydm.widgets import PyDMEmbeddedDisplay
from qtpy import QtWidgets

import haven
from firefly import display


class IocsDisplay(display.FireflyDisplay):
    _ioc_displays = []

    # def __init__(self, config=None):
    #     """Parameters:
    #     ===========

    #     config:
    #       Configuration mapping like that created by
    #       ``haven.load_config()``, which is used by default. Useful
    #       for testing.
    #     """
    #     # Load default haven configuration
    #     if config is None:
    #         self.config = haven.load_config()
    #     else:
    #         self.config = config

    def customize_ui(self):
        # Delete existing IOC widgets
        for idx in reversed(range(self.iocs_layout.count())):
            self.iocs_layout.takeAt(idx).widget().deleteLater()
        # Add embedded displays for all the ion chambers
        self._ioc_displays = []
        manager = haven.registry["beamline_manager"]

        for idx, cpt_name in enumerate(manager.iocs.component_names):
            cpt = getattr(manager.iocs, cpt_name)
            # Add a separator
            if idx > 0:
                line = QtWidgets.QFrame(self.ui)
                line.setObjectName("line")
                # line->setGeometry(QRect(140, 80, 118, 3));
                line.setFrameShape(QtWidgets.QFrame.HLine)
                line.setFrameShadow(QtWidgets.QFrame.Sunken)
                self.iocs_layout.addWidget(line)
            # Create the display object
            disp = PyDMEmbeddedDisplay(parent=self)
            name = cpt.dotted_name.split(".")[-1].lstrip("ioc")
            disp.macros = json.dumps({"IOC": cpt.name, "NAME": name})
            disp.filename = "ioc.ui"
            # Add the Embedded Display to the Results Layout
            self.iocs_layout.addWidget(disp)
            self._ioc_displays.append(disp)

    def ui_filename(self):
        return "iocs.ui"
