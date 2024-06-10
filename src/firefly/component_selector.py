import asyncio
import logging
from collections import OrderedDict
from functools import lru_cache

import qtawesome as qta
from ophyd import (
    Device,
    EpicsMotor,
    PositionerBase,
    Signal,
    do_not_wait_for_lazy_connection,
)
from qasync import QThreadExecutor, asyncSlot
from qtpy.QtGui import QFont, QStandardItem, QStandardItemModel
from qtpy.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QPushButton,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from .application import FireflyApplication

log = logging.getLogger(__name__)


class TreeComponent:
    """Representation of an ophyd Component/Device in a tree view."""

    child_components: list
    dotted_name: str
    component_item: QStandardItem
    type_item: QStandardItem

    def __init__(self, *args, device, text, parent, registry=None, **kwargs):
        self.device = device
        self.text = text
        self.parent = parent
        # Set the associated
        self.set_items()

    def __str__(self):
        return self.dotted_name

    @staticmethod
    @lru_cache()
    def icons():
        """Produce a dictionary of icons for specific device classes.

        Profiling shows that creating the qta.icon objects is
        slow. Since there are a lot of potential signals, it makes
        sense to cache the icons behind a static method to speed up
        window loading.

        """
        return OrderedDict(
            {
                EpicsMotor: qta.icon("mdi.cog-clockwise"),
                Device: qta.icon("mdi.router-network"),
                Signal: qta.icon("mdi.connection"),
            }
        )

    def component_from_dotted_name(self, name):
        if name == self.dotted_name:
            # It's this component, so just return
            return self
        if self.dotted_name not in name:
            # It's not in this branch of the tree, so raise an exception
            raise KeyError(name)
        # See if we can find the dotted name farther down the tree
        for cpt in self.child_components:
            try:
                return cpt.component_from_dotted_name(name)
            except KeyError:
                continue
        raise KeyError(name)

    @property
    def dotted_name(self):
        names = []
        obj = self.device
        while obj.parent is not None:
            names.append(obj.attr_name)
            obj = obj.parent
        # Add the root devices name
        names.append(obj.name)
        return ".".join(reversed(names))

    def set_items(self):
        """Add model items to the parent item."""
        self.component_item = QStandardItem(self.text)
        self.parent.appendRow(self.component_item)
        row = self.component_item.row()
        # Create an item for the type of component
        type_name = type(self.device).__name__
        self.type_item = QStandardItem(type_name)
        column = 1
        self.parent.setChild(row, column, self.type_item)
        # Make the component item bold if it's a positioner
        if isinstance(self.device, PositionerBase):
            font = QFont()
            font.setBold(True)
            self.component_item.setFont(font)
        # Decide on an icon for this component
        for cls, icon in self.icons().items():
            if isinstance(self.device, cls):
                self.type_item.setIcon(icon)
                break
        # Keep a reference to the component that created the items
        self.component_item.setData(self)
        self.type_item.setData(self)

    def add_children(self):
        """Add components of the device as branches on the tree."""
        child_names = getattr(self.device, "component_names", [])
        self.child_components = []
        # Add the children
        for name in child_names:
            with do_not_wait_for_lazy_connection(self.device):
                child = self.__class__(
                    device=getattr(self.device, name),
                    text=name,
                    parent=self.component_item,
                )
                self.child_components.append(child)
        # Add the devices children
        for cpt in self.child_components:
            cpt.add_children()


class ComponentTreeModel(QStandardItemModel):
    Component: type = TreeComponent
    root_components: list

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.root_components = []

    def component_from_dotted_name(self, name):
        for cpt in self.root_components:
            try:
                return cpt.component_from_dotted_name(name)
            except KeyError:
                pass
        raise KeyError(name)

    def component_from_index(self, index):
        item = self.itemFromIndex(index)
        return item.data()

    async def update_devices(self, registry):
        parent_item = self.invisibleRootItem()
        self.root_components = []
        devices = sorted(registry.root_devices, key=lambda dev: dev.name.lower())
        for device in devices:
            with do_not_wait_for_lazy_connection(device):
                cpt = self.Component(
                    device=device,
                    text=device.name,
                    parent=parent_item,
                    registry=registry,
                )
                self.root_components.append(cpt)
        # Add all the children for the root components in separate threads
        loop = asyncio.get_running_loop()
        with QThreadExecutor(len(self.root_components)) as exec:
            aws = (
                loop.run_in_executor(exec, cpt.add_children)
                for cpt in self.root_components
            )
            await asyncio.gather(*aws)


class ComboBoxComponent(TreeComponent):
    def set_items(self):
        """Add model items to the parent item."""
        self.component_item = QStandardItem(self.text)
        if isinstance(self.device, PositionerBase):
            # Only include motors, positioners, etc in the combobox
            self.parent.appendRow(self.component_item)

    def add_children(self):
        """Add components of the device as extra options."""
        child_names = getattr(self.device, "component_names", [])
        self.child_components = []
        # Add the children
        for name in child_names:
            dotted_name = ".".join([self.text, name])
            with do_not_wait_for_lazy_connection(self.device):
                child = self.__class__(
                    device=getattr(self.device, name),
                    text=dotted_name,
                    parent=self.parent,
                )
                self.child_components.append(child)
        # Add the devices children
        for cpt in self.child_components:
            cpt.add_children()


class ComponentComboBoxModel(ComponentTreeModel):
    Component: type = ComboBoxComponent


class TreeDialog(QDialog):
    def __init__(self, *args, model, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model
        self.add_widgets()
        self.connect_signals()

    def connect_signals(self):
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def add_widgets(self):
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        # Add the tree view
        tree_view = QTreeView(parent=self)
        tree_view.setModel(self.model)
        main_layout.addWidget(tree_view)
        # Add accept/reject buttons
        buttons_layout = QHBoxLayout()
        main_layout.addLayout(buttons_layout)
        ok_button = QPushButton(parent=self)
        ok_button.setText("OK")
        ok_button.setIcon(qta.icon("fa5s.check"))
        self.ok_button = ok_button
        buttons_layout.addWidget(ok_button)
        cancel_button = QPushButton(parent=self)
        cancel_button.setText("Cancel")
        cancel_button.setIcon(qta.icon("fa5s.times"))
        self.cancel_button = cancel_button
        buttons_layout.addWidget(cancel_button)


class ComponentSelector(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app = FireflyApplication.instance()
        self.create_models()
        self.add_widgets()
        self.connect_signals()
        # Walk through the component tree and build the models
        coro = self.update_devices(self.app.registry)
        self._devices_task = asyncio.ensure_future(coro)

    def current_component(self):
        cpt_name = self.combo_box.currentText()
        return self.app.registry[cpt_name]

    def create_models(self):
        self.tree_model = ComponentTreeModel(0, 2)
        self.tree_model.setHorizontalHeaderLabels(["Component", "Type"])
        self.combo_box_model = ComponentComboBoxModel(0, 1)

    def connect_signals(self):
        self.tree_button.toggled.connect(self.tree_view.setVisible)
        self.combo_box.currentTextChanged.connect(self.update_tree_model)
        self.tree_view.selectionModel().currentChanged.connect(
            self.update_combo_box_model
        )
        self.app.registry_changed.connect(self.update_devices)

    def update_tree_model(self, new_name):
        log.debug(f"Updating tree: {new_name=}")
        selection = self.tree_view.selectionModel()
        try:
            component = self.tree_model.component_from_dotted_name(new_name)
        except KeyError:
            # It's not a real component, so give up
            log.debug(f"Could not find component for {new_name}, skipping.")
            return
        log.debug(f"Selecting combobox entry: {component.component_item.text()}")
        selection.setCurrentIndex(
            component.component_item.index(), selection.ClearAndSelect | selection.Rows
        )

    def update_combo_box_model(self, index, previous):
        cpt = self.tree_model.component_from_index(index)
        self.combo_box.setCurrentText(cpt.dotted_name)
        log.debug(f"Updating combobox: {cpt.dotted_name=}")

    def select_tree_motor(self):
        if not self.tree_button.isChecked():
            return
        log.debug("Showing motor tree dialog.")
        # Prompt the user to choose a new motor/signal
        accepted = self.tree_dialog.exec()
        self.tree_button.setChecked(False)
        if not accepted:
            # Clicked "Cancel"
            log.debug("Motor tree dialog canceled")
            return
        # Change the current combobox entry
        log.debug("Changing selected motor.")

    @asyncSlot(object)
    async def update_devices(self, registry):
        await self.combo_box_model.update_devices(registry)
        await self.tree_model.update_devices(registry)
        # Clear the combobox text so it doesn't auto-select the first entry
        self.combo_box.setCurrentText("")

    def add_widgets(self):
        # Create a layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        row_layout = QHBoxLayout()
        layout.addLayout(row_layout)
        # Add a combobox
        combo_box = QComboBox(parent=self)
        combo_box.setModel(self.combo_box_model)
        row_layout.addWidget(combo_box)
        combo_box.setEditable(True)
        self.combo_box = combo_box
        # Add a button for launching the tree modal dialog
        tree_button = QToolButton(parent=self)
        tree_button.setIcon(qta.icon("mdi.file-tree"))
        tree_button.setCheckable(True)
        row_layout.addWidget(tree_button)
        self.tree_button = tree_button
        # Add a hidden tree view for selecting motors
        tree_view = QTreeView(parent=self)
        tree_view.setVisible(False)
        tree_view.setModel(self.tree_model)
        layout.addWidget(tree_view)
        self.tree_view = tree_view
