import logging
from collections import namedtuple
from functools import partial
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd
import pyqtgraph as pg
import qtawesome as qta
from qtpy import QtCore, QtWidgets, uic

axes = namedtuple("axes", ("z", "y", "x"))

log = logging.getLogger(__name__)


class FramesetImageView(pg.ImageView):
    def __init__(self, *args, view=None, **kwargs):
        if view is None:
            view = pg.PlotItem()
        super().__init__(*args, view=view, **kwargs)
        self.timeLine.setPen((255, 0, 255, 200), width=5)
        self.timeLine.setHoverPen("r", width=5)

    @QtCore.Slot()
    def roiChanged(self):
        super().roiChanged()
        for curve in self.roiCurves:
            curve.setPen("k")


class FramesetView(QtWidgets.QWidget):
    ui_file = Path(__file__).parent / "frameset_view.ui"
    spectra: np.ndarray | None = None
    aggregators = {
        "Mean": np.mean,
        "Median": np.median,
        "StDev": np.std,
    }
    datasets: dict[str, np.ndarray] | None = None
    data_frames: dict[str, pd.DataFrame] | None = None

    dataset_selected = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = uic.loadUi(self.ui_file, self)
        # Set up control widgets
        self.ui.dataset_combobox.currentTextChanged.connect(self.select_dataset)
        self.ui.time_signal_combobox.currentTextChanged.connect(self.plot_datasets)
        self.button_groups = [  # One for each plotting dimension
            QtWidgets.QButtonGroup(),
            QtWidgets.QButtonGroup(),
            QtWidgets.QButtonGroup(),
        ]
        for grp in self.button_groups:
            grp.setExclusive(False)  # Handled by a slot
        self.ui.lock_aspect_button.toggled.connect(
            self.frame_view.getView().setAspectLocked
        )
        self.ui.lock_aspect_button.toggled.connect(self.toggle_lock_icon)
        self.toggle_lock_icon(True)
        # Clear rows from the dimension layout
        for row in range(1, self.row_count(self.ui.dimensions_layout)):
            self.remove_dimension_widgets(row)
        # Set a default layout for the vertical splitter
        self.ui.sidebar_splitter.setStretchFactor(0, 1)
        self.ui.sidebar_splitter.setStretchFactor(1, 3)

    def toggle_lock_icon(self, state: bool):
        """Toggle the lock icon on the lock aspect button."""
        if state:
            icon = qta.icon("fa.lock")
        else:
            icon = qta.icon("fa.unlock")
        self.ui.lock_aspect_button.setIcon(icon)

    def select_dataset(self, new_dataset: str | None):
        self.frame_view.clear()
        self.enable(False)
        if new_dataset not in [None, ""]:
            self.dataset_selected.emit(new_dataset)

    def row_count(self, layout: QtWidgets.QGridLayout) -> int:
        """How many rows in *layout* actually contain widgets."""
        rows = 0
        for i in range(layout.count()):
            row, _, span, _ = layout.getItemPosition(i)
            rows = max(rows, row + span)
        return rows

    def remove_dimension_widgets(self, row_idx: int):
        layout = self.ui.dimensions_layout
        for col in range(layout.columnCount()):
            item = layout.itemAtPosition(row_idx, col)
            layout.removeItem(item)

    def add_dimension_widgets(self, row_idx: int):
        layout = self.ui.dimensions_layout
        dim_label = QtWidgets.QLabel()
        dim_idx = row_idx - 1
        dim_label.setText(str(dim_idx))
        layout.addWidget(dim_label, row_idx, 0)
        shape_label = QtWidgets.QLabel()
        layout.addWidget(shape_label, row_idx, 1)
        # Dimension check boxes
        buttons = {}
        for col_idx, btn_group in zip(range(2, 5), self.button_groups):
            btn = QtWidgets.QCheckBox()
            btn.setAutoExclusive(False)
            layout.addWidget(btn, row_idx, col_idx)
            btn_group.addButton(btn, dim_idx)
            buttons[col_idx] = btn
        # Combobox for aggregation
        combobox = QtWidgets.QComboBox()
        layout.addWidget(combobox, row_idx, 5)
        combobox.addItems(self.aggregators.keys())
        combobox.currentTextChanged.connect(self.plot_datasets)
        # See if we should check a box by default
        if dim_idx < 3 and self.button_groups[dim_idx].checkedId() == -1:
            layout.itemAtPosition(row_idx, dim_idx + 2).widget().setChecked(True)
            combobox.setEnabled(False)
        # Connect signals for changing dimensions
        for col_idx, btn in buttons.items():
            btn.toggled.connect(
                partial(self.toggle_dimension_widgets, row_idx=row_idx, col_idx=col_idx)
            )

    def toggle_dimension_widgets(self, checked: bool, row_idx: int, col_idx: int):
        """Disable or uncheck widgets that are not available when a radio button is checked."""
        layout = self.ui.dimensions_layout
        if checked:
            row_count = self.row_count(self.ui.dimensions_layout) - 1
            # Uncheck other rows
            other_rows = [r for r in range(1, row_count + 1) if r != row_idx]
            for ri in other_rows:
                btn = layout.itemAtPosition(ri, col_idx).widget()
                btn.setChecked(False)
            # Uncheck other columns
            other_cols = [c for c in range(2, 5) if c != col_idx]
            for ci in other_cols:
                btn = layout.itemAtPosition(row_idx, ci).widget()
                btn.setChecked(False)
        # Enable/disable the aggregate combobox for this row
        btns = [layout.itemAtPosition(row_idx, c).widget() for c in range(2, 5)]
        buttons_checked = any([btn.isChecked() for btn in btns])
        combobox = layout.itemAtPosition(row_idx, 5).widget()
        combobox.setEnabled(not buttons_checked)
        # Update the plots
        self.plot_datasets()

    def set_dimension_widgets(self, row_idx: int, shape: int):
        layout = self.ui.dimensions_layout
        shape_label = layout.itemAtPosition(row_idx, 1).widget()
        shape_label.setText(str(shape))

    def update_signal_widgets(
        self, data_keys: Mapping, independent_hints: Sequence, dependent_hints: Sequence
    ):
        """Update the UI based on new data keys and hints."""
        # Save data keys for later
        self.independent_hints = independent_hints
        self.dependent_hints = dependent_hints
        self.data_keys = data_keys
        self.array_keys = {
            key: props for key, props in data_keys.items() if props["dtype"] == "array"
        }
        self.signal_keys = {
            key: props for key, props in data_keys.items() if props["dtype"] == "number"
        }
        # Set up widgets with new data keys
        combobox = self.ui.dataset_combobox
        combobox.clear()
        combobox.addItems(self.array_keys.keys())
        print(self.signal_keys.keys())
        combobox = self.ui.time_signal_combobox
        combobox.clear()
        combobox.addItems(self.signal_keys.keys())

    @QtCore.Slot()
    @QtCore.Slot(dict)
    def plot_datasets(self, datasets: dict[str, np.ndarray] | None = None):
        """Plot a set of datasets as lines.

        If *datasets* is not given, the last datasets seen are used.

        """
        if datasets is None:
            datasets = self.datasets
        else:
            self.datasets = datasets
        # Clear the plot if there's nothing to show
        im_plot = self.ui.frame_view
        if datasets is None:
            im_plot.clear()
            self.enable(False)
            return
        # Make sure it's just one dataset
        if len(datasets) > 1:
            log.warning(
                "Cannot plot framesets for multiple scans. Please submit an issue to request this feature."
            )
            return
        elif len(datasets) == 1:
            dataset = list(datasets.values())[0]
        elif len(datasets) == 0:
            return
        else:
            raise RuntimeError(f"Malformed input: {datasets}")
        self.update_dimension_widgets(shape=dataset.shape)
        dataset = self.reduce_dimensions(dataset)
        # Determine how to plot the time series values
        tsignal = self.ui.time_signal_combobox.currentText()
        try:
            tvals = self.data_frames[tsignal].values
        except TypeError:
            tvals = None
        # Plot the images
        if 2 <= dataset.ndim <= 3:
            self.enable()
            im_plot.setImage(dataset, xvals=tvals)
        else:
            log.info(f"Skipping plot of frames with shape {dataset.shape}.")
            im_plot.clear()
            self.enable_plots(False)

    def enable(self, enabled: bool = True):
        self.enable_plots(enabled)
        self.dimensions_layout.setEnabled(enabled)

    def enable_plots(self, enabled: bool = True):
        self.ui.plotting_tabs.setEnabled(enabled)

    def update_dimension_widgets(self, shape: tuple[int]):
        """Update the widgets for setting dimensions to match the
        *dataset* array.

        """
        # Build the dimensions layout
        dim_count = len(shape)
        row_count = self.row_count(self.ui.dimensions_layout) - 1
        for row in range(dim_count, row_count):
            self.remove_dimension_widgets(row + 1)
        for row in range(row_count, dim_count):
            self.add_dimension_widgets(row + 1)
        for row in range(dim_count):
            self.set_dimension_widgets(row + 1, shape=shape[row])

    def reduce_dimensions(self, dataset: np.ndarray) -> np.ndarray:
        """Reduce the input *dataset* to a shape for plotting
        depending on the dimensions widgets.

        """
        layout = self.ui.dimensions_layout
        # Apply aggregators
        axes_to_drop = []
        for dim in range(dataset.ndim):
            row = dim + 1
            is_plotted = any(
                [
                    layout.itemAtPosition(row, col).widget().isChecked()
                    for col in range(2, 5)
                ]
            )
            if not is_plotted:
                agg_name = layout.itemAtPosition(row, 5).widget().currentText()
                aggregator = self.aggregators[agg_name]
                dataset = aggregator(dataset, axis=dim, keepdims=True)
                axes_to_drop.append(dim)
        # Order axes according to (z, y, x) widgets
        to = [d for d in range(dataset.ndim) if d not in axes_to_drop]
        frm = [grp.checkedId() for grp in self.button_groups]
        frm = [dim for dim in frm if dim != -1]
        dataset = np.moveaxis(dataset, frm, to)
        # Remove axes that were reduced
        dataset = np.squeeze(dataset, axis=tuple(axes_to_drop))
        return dataset

    def stash_data_frames(self, data_frames: dict[str : pd.DataFrame]):
        if len(data_frames) > 1:
            log.warning(
                "Cannot plot framesets for multiple scans. Please submit an issue to request this feature."
            )
        elif len(data_frames) == 1:
            data_frames = list(data_frames.values())[0]
        elif len(data_frames) == 0:
            return
        self.data_frames = data_frames
