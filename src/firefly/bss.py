import logging

import qtawesome as qta
from apsbss import apsbss
from dm.common.exceptions.objectNotFound import ObjectNotFound
from qtpy.QtCore import Signal
from qtpy.QtGui import QStandardItem, QStandardItemModel

import haven
from firefly import display

log = logging.getLogger(__name__)


class BssDisplay(display.FireflyDisplay):
    """A PyDM display for the beamline scheduling system (BSS)."""

    _proposal_col_names = ["ID", "Title", "Start", "End", "Users", "Badges"]
    _esaf_col_names = [
        "ID",
        "Title",
        "Start",
        "End",
        "Users",
        "Badges",
    ]
    _esaf_id: str = ""
    _psoporsal_id: str = ""

    # Signal
    proposal_changed = Signal()
    proposal_selected = Signal()
    esaf_changed = Signal()
    esaf_selected = Signal()

    def __init__(self, api=apsbss, args=None, macros={}, **kwargs):
        self.api = api
        super().__init__(args=args, macros=macros, **kwargs)
        # Load data models for proposals and ESAFs
        self.load_models()

    def customize_ui(self):
        super().customize_ui()
        icon = qta.icon("fa5s.arrow-right")
        self.ui.update_proposal_button.setIcon(icon)
        self.ui.update_proposal_button.clicked.connect(self.update_proposal)
        self.ui.update_esaf_button.setIcon(icon)
        self.ui.update_esaf_button.clicked.connect(self.update_esaf)
        self.ui.refresh_models_button.clicked.connect(self.load_models)
        # Icon for the refresh button
        self.ui.refresh_models_button.setIcon(qta.icon("fa5s.sync"))

    def customize_device(self):
        self._device = haven.registry.find("beamline_manager")

    def proposals(self):
        config = haven.load_config()
        proposals = []
        beamline = self._device.bss.proposal.beamline_name.get()
        cycle = self._device.bss.esaf.aps_cycle.get()
        # Get proposal data from the API
        try:
            api_result = self.api.listProposals(cycle, beamline)
        except ObjectNotFound:
            api_result = []
        # Parse the API payload into the format for the BSS IOC
        for proposal in api_result:
            users = proposal["experimenters"]
            proposals.append(
                {
                    "Title": proposal["title"],
                    "ID": proposal["id"],
                    "Start": proposal["startTime"],
                    "End": proposal["endTime"],
                    "Users": ", ".join([usr["lastName"] for usr in users]),
                    "Badges": ", ".join([usr["badge"] for usr in users]),
                }
            )
        return proposals

    def esafs(self):
        config = haven.load_config()
        esafs_ = []
        beamline = self._device.bss.proposal.beamline_name.get()
        cycle = self._device.bss.esaf.aps_cycle.get()
        # Retrieve current ESAFS from data management API
        try:
            api_result = self.api.listESAFs(cycle, beamline.split("-")[0])
        except (ObjectNotFound, KeyError):
            api_result = []
        # Parse the API data into a format usable by the BSS IOC
        for esaf in api_result:
            users = esaf["experimentUsers"]
            esafs_.append(
                {
                    "Title": esaf["esafTitle"],
                    "ID": esaf["esafId"],
                    "Start": esaf["experimentStartDate"],
                    "End": esaf["experimentEndDate"],
                    "Users": ", ".join([usr["lastName"] for usr in users]),
                    "Badges": ", ".join([usr["badge"] for usr in users]),
                }
            )
        return esafs_

    def load_models(self):
        config = haven.load_config()
        # Create proposal model object
        col_names = self._proposal_col_names
        self.proposal_model = QStandardItemModel()
        self.proposal_model.setHorizontalHeaderLabels(col_names)
        # Load individual proposals
        proposals = self.proposals()
        for proposal in proposals:
            items = [QStandardItem(str(proposal[col])) for col in col_names]
            self.proposal_model.appendRow(items)
        self.ui.proposal_view.setModel(self.proposal_model)
        # Create proposal model object
        col_names = self._esaf_col_names
        self.esaf_model = QStandardItemModel()
        self.esaf_model.setHorizontalHeaderLabels(col_names)
        # Load individual esafs
        esafs = self.esafs()
        for esaf in esafs:
            items = [QStandardItem(str(esaf[col])) for col in col_names]
            self.esaf_model.appendRow(items)
        self.ui.esaf_view.setModel(self.esaf_model)
        # Connect slots for when proposal/ESAF is changed
        self.ui.proposal_view.selectionModel().currentChanged.connect(
            self.select_proposal
        )
        self.ui.esaf_view.selectionModel().currentChanged.connect(self.select_esaf)

    def select_proposal(self, current, previous):
        # Determine which proposal was selected
        id_col_idx = self._proposal_col_names.index("ID")
        new_id = current.siblingAtColumn(id_col_idx).data()
        self._proposal_id = new_id
        # Enable controls for updating the metadata
        self.ui.update_proposal_button.setEnabled(True)
        self.proposal_selected.emit()

    def update_proposal(self):
        new_id = self._proposal_id
        # Change the proposal in the EPICS record
        bss = haven.registry.find("beamline_manager.bss")
        bss.proposal.proposal_id.set(new_id).wait()
        # Notify any interested parties that the proposal has been changed
        self.proposal_changed.emit()

    def select_esaf(self, current, previous):
        # Determine which esaf was selected
        id_col_idx = self._esaf_col_names.index("ID")
        new_id = current.siblingAtColumn(id_col_idx).data()
        self._esaf_id = new_id
        # Enable controls for updating the metadata
        self.ui.update_esaf_button.setEnabled(True)
        self.esaf_selected.emit()

    def update_esaf(self):
        new_id = self._esaf_id
        # Change the esaf in the EPICS record
        bss = haven.registry.find("beamline_manager.bss")
        bss.wait_for_connection()
        bss.esaf.esaf_id.set(new_id).wait(timeout=5)
        # Notify any interested parties that the esaf has been changed
        self.esaf_changed.emit()

    def ui_filename(self):
        return "bss.ui"


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
