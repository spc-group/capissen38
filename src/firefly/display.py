import subprocess
from pathlib import Path
from typing import Optional, Sequence

from ophyd import Device
from pydm import Display
from qtpy import QtWidgets
from qtpy.QtCore import Signal, Slot

from haven import beamline


class FireflyDisplay(Display):
    caqtdm_ui_file: str = ""
    caqtdm_command: str = "/APSshare/bin/caQtDM -style plastique -noMsg -attach"
    caqtdm_actions: Sequence
    device: Optional[Device]
    registry = None

    # Signals
    status_message_changed = Signal(str, int)
    queue_item_submitted = Signal(object)

    def __init__(self, parent=None, args=None, macros=None, ui_filename=None, **kwargs):
        super().__init__(
            parent=parent, args=args, macros=macros, ui_filename=ui_filename, **kwargs
        )
        self.customize_device()
        self.customize_ui()
        self.prepare_caqtdm_actions()

    def prepare_caqtdm_actions(self):
        """Create QActions for opening caQtDM panels.

        By default, this method creates one action if
        *self.caqtdm_ui_file* is set. Individual displays should
        override this method to add their own QActions. Any actions
        added to the *self.caqtdm_actions* list will be added to the
        "Setup" menu if the display is the root display in a main
        window.

        """
        self.caqtdm_actions = []
        if self.caqtdm_ui_file != "":
            # Create an action for launching a single caQtDM file
            action = QtWidgets.QAction(self)
            action.setObjectName("launch_caqtdm_action")
            action.setText("ca&QtDM")
            action.triggered.connect(self.launch_caqtdm)
            try:
                tooltip = f"Launch the caQtDM panel for {self.device.name}"
            except AttributeError:
                tooltip = "Launch the caQtDM panel for this display."
            action.setToolTip(tooltip)
            self.caqtdm_actions.append(action)

    def _all_children(self, widget):
        for child in widget.children():
            yield widget
            yield from self._all_children(widget=child)

    def find_plan_widgets(self):
        """Look through widgets and determine if any of them are used for
        bluesky plans.

        """
        # from pprint import pprint
        # pprint([c.objectName() for c in self._all_children(self)])
        # for child in self.ui.children():
        #     if child.objectName() == "set_energy_button":
        #         print(f"**{child.objectName()}**")
        #     else:
        #         print(child.objectName())

    def _open_caqtdm_subprocess(self, cmds, *args, **kwargs):
        """Launch a new subprocess and save it to self._caqtdm_process."""
        # Try to leave this as just a simple call to Popen.
        # It helps simplify testing
        self._caqtdm_process = subprocess.Popen(cmds, *args, **kwargs)

    @Slot()
    def launch_caqtdm(self, macros={}, ui_file: str = None):
        """Launch a caQtDM window showing the window's panel."""
        if ui_file is None:
            ui_file = self.caqtdm_ui_file
        cmds = self.caqtdm_command.split()
        # Add macros
        macro_str = ",".join(f"{key}={val}" for key, val in macros.items())
        if macro_str != "":
            cmds.extend(["-macro", macro_str])
        # Add the path to caQtDM .ui file
        cmds.append(ui_file)
        self._open_caqtdm_subprocess(cmds)

    async def update_devices(self, registry):
        """The list of accessible devices has changed."""
        self.registry = registry

    def customize_device(self):
        # Retrieve the device
        device = self.macros().get("DEVICE")
        if device is not None:
            device = beamline.devices[device]
        self.device = device
        return device

    def customize_ui(self):
        pass

    def update_queue_status(self, status):
        pass

    def show_message(self, message: str, timeout: int = 0):
        """Display a message in the status bar."""
        self.status_message_changed.emit(str(message), timeout)

    def ui_filename(self):
        raise NotImplementedError

    def ui_filepath(self):
        path_base = Path(__file__).parent
        return path_base / self.ui_filename()


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
