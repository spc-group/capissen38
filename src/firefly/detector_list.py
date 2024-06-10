from PyQt5.QtGui import QStandardItem, QStandardItemModel
from qtpy.QtWidgets import QAbstractItemView, QListView

from haven import registry


class DetectorListView(QListView):
    detector_model: QStandardItemModel

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_detector_items()
        # Make it possible to select multiple detectors
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)

    def load_detector_items(self):
        detectors = registry.findall(label="detectors", allow_none=True)
        self.detector_model = QStandardItemModel()
        self.setModel(self.detector_model)
        for det in detectors:
            self.detector_model.appendRow(QStandardItem(det.name))

    def selected_detectors(self):
        indexes = self.selectedIndexes()
        items = [self.detector_model.itemFromIndex(i) for i in indexes]
        names = [item.text() for item in items]
        return names


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
