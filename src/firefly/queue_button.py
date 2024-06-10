"""A QPushButton that responds to the state of the queue server."""

import qtawesome as qta
from qtpy import QtGui, QtWidgets

from firefly import FireflyApplication


class QueueButton(QtWidgets.QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initially disable the button until the status of the queue can be determined
        self.setDisabled(True)
        # Listen for changes to the run engine
        app = FireflyApplication.instance()
        app.queue_status_changed.connect(self.handle_queue_status_change)

    def handle_queue_status_change(self, status: dict):
        if status["worker_environment_exists"]:
            self.setEnabled(True)
        else:
            # Should be disabled because the queue is closed
            self.setDisabled(True)
        # Coloration for the whether the item would get run immediately
        app = FireflyApplication.instance()
        if status["re_state"] == "idle" and app.queue_autostart_action.isChecked():
            # Will play immediately
            self.setStyleSheet(
                "background-color: rgb(25, 135, 84);\nborder-color: rgb(25, 135, 84);"
            )
            self.setIcon(qta.icon("fa5s.play"))
            self.setText("Run")
            self.setToolTip("Add this plan to the queue and start it immediately.")
        elif status["worker_environment_exists"]:
            # Will be added to the queue
            self.setStyleSheet(
                "background-color: rgb(0, 123, 255);\nborder-color: rgb(0, 123, 255);"
            )
            self.setIcon(qta.icon("fa5s.list"))
            self.setText("Add to Queue")
            self.setToolTip("Add this plan to the queue to run later.")
        else:
            # Regular old (probably disabled) button
            self.setStyleSheet("")
            self.setIcon(QtGui.QIcon())


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
