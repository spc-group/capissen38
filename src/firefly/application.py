import asyncio
import logging
import subprocess
from collections import OrderedDict
from functools import partial
from pathlib import Path
from typing import Mapping, Sequence

import pydm
import pyqtgraph as pg
import qtawesome as qta
from ophydregistry import Registry
from pydm.application import PyDMApplication
from pydm.utilities.stylesheet import apply_stylesheet
from PyQt5.QtWidgets import QStyleFactory
from qtpy import QtCore, QtWidgets
from qtpy.QtCore import Signal
from qtpy.QtWidgets import QAction

from haven import load_config
from haven import load_instrument as load_haven_instrument
from haven import registry
from haven.exceptions import ComponentNotFound
from haven.instrument.device import titelize

from .main_window import FireflyMainWindow, PlanMainWindow
from .queue_client import QueueClient, queueserver_api

generator = type((x for x in []))

__all__ = ["ui_dir", "FireflyApplication"]


log = logging.getLogger(__name__)


ui_dir = Path(__file__).parent


pg.setConfigOption("background", (252, 252, 252))
pg.setConfigOption("foreground", (0, 0, 0))


class FireflyApplication(PyDMApplication):
    default_display = None
    xafs_scan_window = None

    # For keeping track of ophyd devices used by the Firefly
    registry: Registry = None
    registry_changed = Signal(Registry)

    # Actions for showing window
    show_status_window_action: QtWidgets.QAction
    show_runs_window_action: QtWidgets.QAction
    show_energy_window_action: QtWidgets.QAction
    show_bss_window_action: QtWidgets.QAction
    show_voltmeters_window_action: QtWidgets.QAction
    show_logs_window_action: QtWidgets.QAction
    launch_queuemonitor_action: QtWidgets.QAction

    # Keep track of motors
    motor_actions: Sequence = []
    motor_window_slots: Sequence = []

    # Keep track of plans
    plan_actions: Sequence = []

    # Keep track of cameras
    camera_actions: Mapping = {}
    camera_window_slots: Sequence

    # Keep track of area detectors
    area_detector_actions: Mapping = {}
    area_detector_window_slots: Sequence

    # Keep track of slits
    slits_actions: Mapping = {}
    slits_window_slots: Sequence

    # Keep track of XRF detectors
    xrf_detector_actions: Mapping = {}
    xrf_detector_window_slots: Sequence

    # Signals for running plans on the queueserver
    queue_item_added = Signal(object)

    # Signals responding to queueserver changes
    queue_length_changed = Signal(int)
    queue_status_changed = Signal(dict)
    queue_environment_opened = Signal(bool)  # Opened or closed
    queue_environment_state_changed = Signal(str)  # New state
    queue_manager_state_changed = Signal(str)  # New state
    queue_re_state_changed = Signal(str)  # New state
    # queue_devices_changed = Signal(dict)  # New list of devices

    # Actions for controlling the queueserver
    start_queue_action: QAction
    pause_runengine_action: QAction
    pause_runengine_now_action: QAction
    resume_runengine_action: QAction
    stop_runengine_action: QAction
    abort_runengine_action: QAction
    halt_runengine_action: QAction
    start_queue: QAction
    queue_autostart_action: QAction
    queue_open_environment_action: QAction
    check_queue_status_action: QAction

    def __init__(self, display="status", use_main_window=False, *args, **kwargs):
        # Instantiate the parent class
        # (*ui_file* and *use_main_window* let us render the window here instead)
        self.default_display = display
        super().__init__(ui_file=None, use_main_window=use_main_window, *args, **kwargs)
        qss_file = Path(__file__).parent / "firefly.qss"
        self.setStyleSheet(qss_file.read_text())
        log.info(f"Available styles: {QStyleFactory.keys()}")
        # self.setStyle("Adwaita-dark")
        # qdarktheme.setup_theme(additional_qss=qss_file.read_text())
        self.windows = OrderedDict()
        self.queue_re_state_changed.connect(self.enable_queue_controls)
        self.registry = registry

    def __del__(self):
        if hasattr(self, "_queue_thread"):
            self._queue_thread.quit()
            self._queue_thread.wait(msecs=5000)
            assert not self._queue_thread.isRunning()

    def _setup_window_action(self, action_name: str, text: str, slot: QtCore.Slot):
        action = QtWidgets.QAction(self)
        action.setObjectName(action_name)
        action.setText(text)
        action.triggered.connect(slot)
        setattr(self, action_name, action)
        return action

    def reload_instrument(self, load_instrument=True):
        """(Re)load all the instrument devices."""
        load_haven_instrument(registry=self.registry)
        self.registry_changed.emit(self.registry)

    def setup_instrument(self, load_instrument=True):
        """Set up the application to use a previously loaded instrument.

        Expects devices, plans, etc to have been created already.

        Parameters
        ==========
        load_instrument
          If true, re-read configuration files and create ophyd
          devices. This process is slow.

        Emits
        =====
        registry_changed
          Signal that allows windows to update their widgets for the
          new list of instruments.

        """
        if load_instrument:
            load_haven_instrument(registry=self.registry)
            self.registry_changed.emit(self.registry)
        # Make actions for launching other windows
        self.setup_window_actions()
        # Actions for controlling the bluesky run engine
        self.setup_runengine_actions()
        # Prepare the client for interacting with the queue server
        # self.prepare_queue_client()

    def show_default_window(self):
        """Show the first starting window for the application."""
        # Launch the default display
        show_default_window = getattr(self, f"show_{self.default_display}_window")
        default_window = show_default_window()
        # Set up the window to show list of PV connections
        pydm.utilities.shortcuts.install_connection_inspector(parent=default_window)

    def setup_window_actions(self):
        """Create QActions for clicking on menu items, shortcuts, etc.

        These actions should be usable by multiple
        windows. Window-specific actions belong with the window.

        """
        # Setup actions for the various categories of devices
        self._prepare_device_windows(
            device_label="extra_motors",
            attr_name="motor",
            ui_file="motor.py",
            device_key="MOTOR",
        )
        self._prepare_device_windows(
            device_label="ion_chambers",
            attr_name="ion_chamber",
            ui_file="ion_chamber.py",
            device_key="IC",
        )
        self._prepare_device_windows(
            device_label="cameras",
            attr_name="camera",
            ui_file="area_detector_viewer.py",
            device_key="AD",
        )
        self._prepare_device_windows(
            device_label="area_detectors",
            attr_name="area_detector",
            ui_file="area_detector_viewer.py",
            device_key="AD",
        )
        self._prepare_device_windows(
            device_label="slits",
            attr_name="slits",
            ui_file="slits.py",
            device_key="DEVICE",
            icon=qta.icon("mdi.crop"),
        )
        self._prepare_device_windows(
            device_label="kb_mirrors",
            attr_name="kb_mirrors",
            ui_file="kb_mirrors.py",
            device_key="DEVICE",
            icon=qta.icon("msc.mirror"),
        )
        self._prepare_device_windows(
            device_label="mirrors",
            attr_name="mirror",
            ui_file="mirror.py",
            device_key="DEVICE",
            icon=qta.icon("msc.mirror"),
        )
        self._prepare_device_windows(
            device_label="tables",
            attr_name="table",
            ui_file="table.py",
            device_key="DEVICE",
            icon=qta.icon("mdi.table-furniture"),
        )
        self._prepare_device_windows(
            device_label="xrf_detectors",
            attr_name="xrf_detector",
            ui_file="xrf_detector.py",
            device_key="DEV",
        )
        self._setup_window_action(
            action_name="show_filters_window_action",
            text="Filters",
            slot=self.show_filters_window,
        )
        self.show_filters_window_action.setIcon(qta.icon("mdi.air-filter"))
        # Action for showing the beamline status window
        self._setup_window_action(
            action_name="show_status_window_action",
            text="Beamline Status",
            slot=self.show_status_window,
        )
        # Actions for executing plans
        plans = [
            # (plan_name, text, display file)
            ("count", "&Count", "count.py"),
            ("move_motor", "&Move motor", "move_motor_window.py"),
            ("line_scan", "&Line scan", "line_scan.py"),
            ("grid_scan", "&Grid scan", "grid_scan.py"),
            ("xafs_scan", "&XAFS Scan", "xafs_scan.py"),
        ]
        self.plan_actions = []
        for plan_name, text, display_file in plans:
            slot = partial(
                self.show_plan_window, name=plan_name, display_file=display_file
            )
            action_name = f"show_{plan_name}_plan_window_action"
            # Launch windows for plans
            action = QtWidgets.QAction(self)
            action.setObjectName(action_name)
            action.setText(text)
            action.triggered.connect(slot)
            self.plan_actions.append(action)
        # Action for showing the run browser window
        self._setup_window_action(
            action_name="show_run_browser_action",
            text="Browse Runs",
            slot=self.show_run_browser_window,
        )
        # Action for launch queue-monitor
        self._setup_window_action(
            action_name="launch_queuemonitor_action",
            text="Queue Monitor",
            slot=self.launch_queuemonitor,
        )
        # Action for showing the beamline scheduling window
        self._setup_window_action(
            action_name="show_bss_window_action",
            text="Scheduling (&BSS)",
            slot=self.show_bss_window,
        )
        # Action for shoing the IOC start/restart/stop window
        self._setup_window_action(
            action_name="show_iocs_window_action",
            text="&IOCs",
            slot=self.show_iocs_window,
        )
        # Launch ion chamber voltmeters window
        self._setup_window_action(
            action_name="show_voltmeters_window_action",
            text="&Voltmeters",
            slot=self.show_voltmeters_window,
        )
        # Launch log window
        self._setup_window_action(
            action_name="show_logs_window_action",
            text="Logs",
            slot=self.show_logs_window,
        )
        # Launch energy window
        self._setup_window_action(
            action_name="show_energy_window_action",
            text="Energy",
            slot=self.show_energy_window,
        )
        self.show_energy_window_action.setIcon(qta.icon("mdi.sine-wave"))
        # Launch camera overview
        self._setup_window_action(
            action_name="show_cameras_window_action",
            text="All Cameras",
            slot=self.show_cameras_window,
        )

    def launch_queuemonitor(self):
        config = load_config()["queueserver"]
        zmq_info_addr = f"tcp://{config['info_host']}:{config['info_port']}"
        zmq_ctrl_addr = f"tcp://{config['control_host']}:{config['control_port']}"
        cmds = [
            "queue-monitor",
            "--zmq-control-addr",
            zmq_ctrl_addr,
            "--zmq-info-addr",
            zmq_info_addr,
        ]
        subprocess.Popen(cmds)

    def setup_runengine_actions(self):
        """Create QActions for controlling the bluesky runengine."""
        # Internal actions for interacting with the run engine
        self.check_queue_status_action = QtWidgets.QAction(self)
        # Navbar actions for controlling the run engine
        actions = [
            ("pause_runengine_action", "Pause", "fa5s.stopwatch"),
            ("pause_runengine_now_action", "Pause Now", "fa5s.pause"),
            ("resume_runengine_action", "Resume", "fa5s.play"),
            ("stop_runengine_action", "Stop", "fa5s.stop"),
            ("abort_runengine_action", "Abort", "fa5s.eject"),
            ("halt_runengine_action", "Halt", "fa5s.ban"),
            ("start_queue_action", "Start", "fa5s.play"),
        ]
        self.queue_action_group = QtWidgets.QActionGroup(self)
        for name, text, icon_name in actions:
            action = QtWidgets.QAction(self.queue_action_group)
            icon = qta.icon(icon_name)
            action.setText(text)
            action.setCheckable(True)
            action.setIcon(icon)
            setattr(self, name, action)
        # Actions that control how the queue operates
        actions = [
            # Attr, object name, text
            ("queue_autostart_action", "queue_autostart_action", "&Autoplay"),
            (
                "queue_open_environment_action",
                "queue_open_environment_action",
                "&Open Environment",
            ),
        ]
        for attr, obj_name, text in actions:
            action = QAction()
            action.setObjectName(obj_name)
            action.setText(text)
            setattr(self, attr, action)
        # Customize some specific actions
        self.queue_autostart_action.setCheckable(True)
        self.queue_autostart_action.setChecked(True)
        self.queue_open_environment_action.setCheckable(True)

    def _prepare_device_windows(
        self,
        device_label: str,
        attr_name: str,
        ui_file=None,
        window_slot=None,
        device_key="DEVICE",
        icon=None,
    ):
        """Generic routine to be called for individual classes of devices.

        Sets up window actions, windows and window slots for each
        instance of the this device class (specified by *device_label*).

        For example, to set up device windows for all a Tardis (Ophyd
        devices with the "tardis_ship" label), call:

        .. code:: python

            app._prepare_device_windows(device_label="tardis_ship", attr_name="tardis")

        This will create ``app.tardis_actions``,
        ``app.tardis_window_slots`` and
        ``app.tardis_windows``.

        Parameters
        ==========
        device_label
          The Ophyd label by which to find the devices.
        attr_name
          An arbitrary name to use for keeping track of windows, actions, etc.
        window_slot
          A Qt slot that gets called when an action is triggered. This
          slot receive a *device* positional argument for which it is expected
          to show a new FireflyWindow.
        device_key
          A key to use for the device name in the macros
          dictionary. If *device_key* is "DEVICE" (default), then the
          macros will be {"DEVICE": device.name}. Has no effect if
          *window_slot* is used.
        icon
          A QIcon that will be added to the action.
        """
        # We need a UI file, unless a custom window_slot is given
        if ui_file is None and window_slot is None:
            raise ValueError(
                "Parameters *ui_file* and *window_slot* cannot both be None."
            )
        # Get needed devices from the device registry
        try:
            devices = sorted(
                self.registry.findall(label=device_label), key=lambda x: x.name
            )
        except ComponentNotFound:
            log.warning(f"No {device_label} found, menu will be empty.")
            devices = []
        # Create menu actions for each device
        actions = {}
        setattr(self, f"{attr_name}_actions", actions)
        window_slots = []
        setattr(self, f"{attr_name}_window_slots", window_slots)
        setattr(self, f"{attr_name}_windows", {})
        for device in devices:
            # Create the window action
            action = QtWidgets.QAction(self)
            action.setObjectName(f"action_show_{attr_name}_{device.name}")
            display_text = titelize(device.name)
            action.setText(display_text)
            if icon is not None:
                action.setIcon(icon)
            actions[device.name] = action
            # Create a slot for opening the device window
            if window_slot is not None:
                # A device specific window loader was provided
                slot = partial(window_slot, device=device)
            else:
                # No device specific loader, use the generic loader
                slot = partial(
                    self.show_device_window,
                    device=device,
                    device_label=attr_name,
                    ui_file=ui_file,
                    device_key=device_key,
                )
            action.triggered.connect(slot)
            window_slots.append(slot)

    def prepare_queue_client(self, api=None):
        """Set up the QueueClient object that talks to the queue server.

        Parameters
        ==========
        api
          queueserver API. Used for testing.

        """
        if api is None:
            api = queueserver_api()
        # Create the client object
        client = QueueClient(api=api)
        self.queue_open_environment_action.triggered.connect(client.open_environment)
        self._queue_client = client
        # Connect actions to slots for controlling the queueserver
        self.pause_runengine_action.triggered.connect(
            partial(client.request_pause, defer=True)
        )
        self.pause_runengine_now_action.triggered.connect(
            partial(client.request_pause, defer=False)
        )
        self.start_queue_action.triggered.connect(client.start_queue)
        self.check_queue_status_action.triggered.connect(
            partial(client.check_queue_status, True)
        )
        # Connect signals to slots for executing plans on queueserver
        self.queue_item_added.connect(client.add_queue_item)
        # Connect signals/slots for queueserver state changes
        client.status_changed.connect(self.queue_status_changed)
        client.length_changed.connect(self.queue_length_changed)
        client.environment_opened.connect(self.queue_environment_opened)
        self.queue_environment_opened.connect(self.set_open_environment_action_state)
        client.environment_state_changed.connect(self.queue_environment_state_changed)
        client.manager_state_changed.connect(self.queue_manager_state_changed)
        client.re_state_changed.connect(self.queue_re_state_changed)
        client.devices_changed.connect(self.update_devices_allowed)
        self.queue_autostart_action.toggled.connect(
            self.check_queue_status_action.trigger
        )
        self.queue_autostart_action.toggled.connect(client.toggle_autostart)

    async def start(self):
        """Start the background timers, show the first window, and wait."""
        # Keep an event to know when the app has closed
        self.app_close_event = asyncio.Event()
        self.aboutToQuit.connect(self.app_close_event.set)
        # Show the UI stuffs
        self.show_default_window()
        self.prepare_queue_client()
        self._queue_client.start()
        # Start the actual asyncio event loop
        await self.app_close_event.wait()

    def update_devices_allowed(self, devices):
        pass

    def enable_queue_controls(self, re_state):
        """Enable/disable the navbar buttons that control the queue.

        Most buttons are only relevant when the run engine is in
        certain states. For exmple, you can't click Play if the run
        engine is already running.

        """
        all_actions = [
            self.start_queue_action,
            self.stop_runengine_action,
            self.pause_runengine_action,
            self.pause_runengine_now_action,
            self.resume_runengine_action,
            self.abort_runengine_action,
            self.halt_runengine_action,
        ]
        # Decide which signals to enable
        unknown_re_state = re_state is None or re_state.strip() == ""
        if unknown_re_state:
            # Unknown state, no button should work
            enabled_signals = []
        elif re_state == "idle":
            enabled_signals = [self.start_queue_action]
        elif re_state == "paused":
            enabled_signals = [
                self.stop_runengine_action,
                self.resume_runengine_action,
                self.halt_runengine_action,
                self.abort_runengine_action,
            ]
        elif re_state == "running":
            enabled_signals = [
                self.pause_runengine_action,
                self.pause_runengine_now_action,
            ]
        else:
            raise ValueError(f"Unknown run engine state: {re_state}")
        # Enable/disable the relevant signals
        for action in all_actions:
            action.setEnabled(action in enabled_signals)

    def add_queue_item(self, item):
        log.debug(f"Application received item to add to queue: {item}")
        self.queue_item_added.emit(item)

    def connect_menu_signals(self, window):
        """Connects application-level signals to the associated slots.

        These signals should generally be applicable to multiple
        windows. If the signal and/or slot is specific to a given
        window, then it should be in that widnow's class definition
        and setup code.

        """
        window.actionShow_Sample_Viewer.triggered.connect(
            self.show_sample_viewer_window
        )

    def show_window(self, WindowClass, ui_file, name=None, macros={}):
        # Come up with the default key for saving in the windows dictionary
        if name is None:
            name = f"{WindowClass.__name__}_{ui_file.name}"
        # Check if the window has already been created
        if (w := self.windows.get(name)) is None:
            # Window is not yet created, so create one
            w = self.create_window(WindowClass, ui_dir / ui_file, macros=macros)
            self.windows[name] = w
            # Connect signals to remove the window when it closes
            w.destroyed.connect(partial(self.forget_window, name=name))
        else:
            # Window already exists so just bring it to the front
            w.show()
            w.activateWindow()
        return w

    def forget_window(self, obj, name):
        """Forget this window exists."""
        if hasattr(self, "windows"):
            del self.windows[name]

    def create_window(self, WindowClass, ui_file, macros={}):
        # Create and save this window
        main_window = WindowClass(
            hide_menu_bar=self.hide_menu_bar, hide_status_bar=self.hide_status_bar
        )
        # Make it look pretty
        apply_stylesheet(self.stylesheet_path, widget=main_window)
        main_window.update_tools_menu()
        # Load the UI file for this window
        display = main_window.open(str(ui_file.resolve()), macros=macros)
        self.connect_menu_signals(window=main_window)
        # Show the display
        if self.fullscreen:
            main_window.enter_fullscreen()
        else:
            main_window.show()
        self.check_queue_status_action.trigger()
        return main_window

    def show_device_window(
        self, *args, device, device_label: str, ui_file: str, device_key: str
    ):
        """Instantiate a new main window for the given device.

        This is a generalized version of the more specific slots, such
        as ``self.show_area_detector_window()``.

        It loads a window with the given UI file *ui_file* (relative
        to the ui directory). The macros will be ``{"DEV":
        device.name}``.

        """
        device_pyname = device.name.replace(" ", "_")
        device_title = titelize(device.name)
        self.show_window(
            FireflyMainWindow,
            ui_dir / ui_file,
            name=f"FireflyMainWindow_{device_label}_{device_pyname}",
            macros={device_key: device.name, f"{device_key}_TITLE": device_title},
        )

    def show_status_window(self, stylesheet_path=None):
        """Instantiate a new main window for this application."""
        self.show_window(
            FireflyMainWindow, ui_dir / "status.py", name="beamline_status"
        )

    @QtCore.Slot()
    def show_run_browser_window(self):
        return self.show_window(
            PlanMainWindow, ui_dir / "run_browser.py", name="run_browser"
        )

    @QtCore.Slot()
    def show_logs_window(self):
        self.show_window(FireflyMainWindow, ui_dir / "log_viewer.ui", name="log_viewer")

    @QtCore.Slot()
    def show_xafs_scan_window(self):
        return self.show_window(
            PlanMainWindow, ui_dir / "xafs_scan.py", name="xafs_scan"
        )

    @QtCore.Slot()
    def show_plan_window(self, name: str, display_file: str):
        """Launch a window for a given plan.

        Parameters
        ==========
        name
          Human-readable name for the plan window
        display_file
          Can be the name of .ui file or the .py file for the PyDM
          display.

        """
        return self.show_window(
            PlanMainWindow,
            ui_dir / "plans" / display_file,
            name=f"{name}_plan",
        )

    @QtCore.Slot()
    def show_voltmeters_window(self):
        return self.show_window(
            PlanMainWindow, ui_dir / "voltmeters.py", name="voltmeters"
        )

    @QtCore.Slot()
    def show_sample_viewer_window(self):
        return self.show_window(
            FireflyMainWindow, ui_dir / "sample_viewer.ui", name="sample_viewer"
        )

    @QtCore.Slot()
    def show_cameras_window(self):
        return self.show_window(
            FireflyMainWindow, ui_dir / "cameras.py", name="cameras"
        )

    @QtCore.Slot()
    def show_energy_window(self):
        return self.show_window(PlanMainWindow, ui_dir / "energy.py", name="energy")

    @QtCore.Slot()
    def show_bss_window(self):
        return self.show_window(FireflyMainWindow, ui_dir / "bss.py", name="bss")

    @QtCore.Slot()
    def show_iocs_window(self):
        return self.show_window(FireflyMainWindow, ui_dir / "iocs.py", name="iocs")

    @QtCore.Slot()
    def show_filters_window(self):
        return self.show_window(
            FireflyMainWindow, ui_dir / "filters.py", name="filters"
        )

    @QtCore.Slot(bool)
    def set_open_environment_action_state(self, is_open: bool):
        """Update the readback value for opening the queueserver environment."""
        action = self.queue_open_environment_action
        if action is not None:
            action.blockSignals(True)
            action.setChecked(is_open)
            action.blockSignals(False)


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
