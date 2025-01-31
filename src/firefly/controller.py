import logging
import subprocess
from collections import OrderedDict
from functools import partial
from pathlib import Path

import pydm
import pyqtgraph as pg
import qtawesome as qta
from ophyd_async.core import NotConnected
from ophydregistry import Registry
from qasync import asyncSlot
from qtpy import QtCore, QtWidgets
from qtpy.QtCore import QObject
from qtpy.QtCore import Signal, Slot
from qtpy.QtGui import QIcon, QKeySequence
from qtpy.QtWidgets import QAction, QErrorMessage

from haven import beamline, load_config, tiled_client
from haven.exceptions import ComponentNotFound, InvalidConfiguration
from haven.utils import titleize

from .action import Action, ActionsRegistry, WindowAction
from .kafka_client import KafkaClient
from .main_window import FireflyMainWindow, PlanMainWindow
from .queue_client import QueueClient, queueserver_api

generator = type((x for x in []))

__all__ = ["ui_dir", "FireflyController"]


log = logging.getLogger(__name__)


ui_dir = Path(__file__).parent
plans_dir = ui_dir / "plans"


pg.setConfigOption("background", (252, 252, 252))
pg.setConfigOption("foreground", (0, 0, 0))


class FireflyController(QObject):
    default_display = None

    # For keeping track of ophyd devices
    registry: Registry = None
    registry_changed = Signal(Registry)

    # For keeping track of the various device and window actions
    actions: ActionsRegistry

    # Signals for running plans on the queueserver
    queue_item_added = Signal(object)

    # Signals responding to queueserver documents over kafka
    run_started = Signal(str)
    run_updated = Signal(str)
    run_stopped = Signal(str)

    # Signals responding to queueserver changes
    queue_status_changed = Signal(dict)
    queue_in_use_changed = Signal(bool)  # length > 0, or running
    queue_environment_opened = Signal(bool)  # Opened or closed
    queue_environment_state_changed = Signal(str)  # New state
    queue_manager_state_changed = Signal(str)  # New state
    queue_re_state_changed = Signal(str)  # New state
    queue_empty_changed = Signal(bool)  # Whether queue is empty
    # queue_devices_changed = Signal(dict)  # New list of devices

    def __init__(self, parent=None, display="status", use_main_window=False):
        # Instantiate the parent class
        # (*ui_file* and *use_main_window* let us render the window here instead)
        self.default_display = display
        super().__init__(parent=parent)
        # Initialize needed attributes
        self.actions = ActionsRegistry()
        self.windows = OrderedDict()
        self.queue_re_state_changed.connect(self.enable_queue_controls)
        self.registry = beamline.devices
        # An error message dialog for later use
        self.error_message = QErrorMessage()

    def _setup_window_action(
        self, action_name: str, text: str, slot: QtCore.Slot, shortcut=None, icon=None
    ):
        action = QtWidgets.QAction(self)
        action.setObjectName(action_name)
        action.setText(text)
        action.triggered.connect(slot)
        if shortcut is not None:
            action.setShortcut(QKeySequence(shortcut))
        if icon is not None:
            action.setIcon(qta.icon(icon))
        setattr(self, action_name, action)
        return action

    async def setup_instrument(self, load_instrument=True):
        """Set up the application to use a previously loaded instrument.

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
            beamline.load()
            try:
                await beamline.connect()
            except NotConnected as exc:
                log.exception(exc)
                msg = (
                    "One or more devices failed to load. See console logs for details."
                )
                self.error_message.showMessage(msg)
            self.registry_changed.emit(beamline.devices)
        # Make actions for launching other windows
        self.setup_window_actions()
        # Actions for controlling the bluesky run engine
        self.setup_queue_actions()
        # Inject menu actions into the various windows
        for action in self.actions.all_actions:
            if hasattr(action, "window_created"):
                action.window_created.connect(self.finalize_new_window)

    def show_default_window(self):
        """Show the first starting window for the application."""
        # Launch the default display
        default_window_action = getattr(self.actions, self.default_display)
        default_window = default_window_action.show_window()
        # Set up the window to show list of PV connections
        pydm.utilities.shortcuts.install_connection_inspector(parent=default_window)

    def setup_window_actions(self):
        """Create QActions for clicking on menu items, shortcuts, etc.

        These actions should be usable by multiple
        windows. Window-specific actions belong with the window.

        """
        # Setup actions for the various categories of devices
        self.actions.motors = self.device_actions(
            device_label="extra_motors",
            display_file=ui_dir / "motor.py",
            device_key="MOTOR",
        )
        self.actions.ion_chambers = self.device_actions(
            device_label="ion_chambers",
            display_file=ui_dir / "ion_chamber.py",
            device_key="IC",
        )
        self.actions.cameras = self.device_actions(
            device_label="cameras",
            display_file=ui_dir / "area_detector_viewer.py",
            device_key="AD",
        )
        self.actions.area_detectors = self.device_actions(
            device_label="area_detectors",
            display_file=ui_dir / "area_detector_viewer.py",
            device_key="AD",
        )
        self.actions.slits = self.device_actions(
            device_label="slits",
            display_file=ui_dir / "slits.py",
            device_key="DEVICE",
            icon=qta.icon("mdi.crop"),
        )
        self.actions.mirrors = self.device_actions(
            device_label="mirrors",
            display_file=ui_dir / "mirror.py",
            device_key="DEVICE",
            icon=qta.icon("msc.mirror"),
        )
        self.actions.mirrors.update(
            self.device_actions(
                device_label="kb_mirrors",
                display_file=ui_dir / "kb_mirrors.py",
                device_key="DEVICE",
                icon=qta.icon("msc.mirror"),
            )
        )
        self.actions.tables = self.device_actions(
            device_label="tables",
            display_file=ui_dir / "table.py",
            device_key="DEVICE",
            icon=qta.icon("mdi.table-furniture"),
        )
        self.actions.robots = self.device_actions(
            device_label="robots",
            display_file=ui_dir / "robot.py",
            device_key="DEVICE",
            WindowClass=PlanMainWindow,
            icon=qta.icon("mdi.robot-industrial"),
        )
        self.actions.xrf_detectors = self.device_actions(
            device_label="xrf_detectors",
            display_file=ui_dir / "xrf_detector.py",
            device_key="DEV",
        )
        self.actions.xray_filter = WindowAction(
            name="show_filters_window_action",
            text="Filters",
            display_file=ui_dir / "filters.py",
            WindowClass=FireflyMainWindow,
            icon=qta.icon("mdi.air-filter"),
        )
        # Action for showing the beamline status window
        self.actions.status = WindowAction(
            name="show_status_window_action",
            text="Beamline Status",
            display_file=ui_dir / "status.py",
            WindowClass=PlanMainWindow,
        )
        self.actions.status.window_created.connect(self.finalize_status_window)
        # Actions for executing plans
        self.actions.plans = {
            "count": WindowAction(
                name="count",
                text="&Count",
                display_file=plans_dir / "count.py",
                shortcut="Ctrl+Shift+C",
                icon=qta.icon("mdi.numeric"),
                WindowClass=PlanMainWindow,
            ),
            "move_motor": WindowAction(
                name="move_motor",
                text="&Move motor",
                display_file=plans_dir / "move_motor_window.py",
                shortcut="Ctrl+Shift+M",
                icon=qta.icon("mdi.rotate-right-variant"),
                WindowClass=PlanMainWindow,
            ),
            "line_scan": WindowAction(
                name="line_scan",
                text="&Line scan",
                display_file=plans_dir / "line_scan.py",
                shortcut="Ctrl+Shift+L",
                icon=qta.icon("mdi.chart-bell-curve"),
                WindowClass=PlanMainWindow,
            ),
            "grid_scan": WindowAction(
                name="grid_scan",
                text="&Grid scan",
                shortcut="Ctrl+Shift+G",
                display_file=plans_dir / "grid_scan.py",
                icon=qta.icon("mdi.grid"),
                WindowClass=PlanMainWindow,
            ),
            "xafs_scan": WindowAction(
                name="xafs_scan",
                text="&XAFS scan",
                display_file=plans_dir / "xafs_scan.py",
                shortcut="Ctrl+Shift+X",
                icon=qta.icon("mdi.chart-bell-curve-cumulative"),
                WindowClass=PlanMainWindow,
            ),
        }

        # Action for showing the run browser window
        self.actions.run_browser = WindowAction(
            name="show_run_browser_action",
            text="Browse Runs",
            display_file=ui_dir / "run_browser" / "display.py",
            shortcut="Ctrl+Shift+B",
            icon=qta.icon("mdi.book-open-variant"),
            WindowClass=FireflyMainWindow,
        )
        self.actions.run_browser.window_created.connect(
            self.finalize_run_browser_window
        )
        # Action for showing the beamline scheduling window
        self.actions.bss = WindowAction(
            name="show_bss_window_action",
            text="Scheduling (&BSS)",
            display_file=ui_dir / "bss.py",
            WindowClass=FireflyMainWindow,
            icon=qta.icon("fa5s.calendar"),
        )
        # Action for shoing the IOC start/restart/stop window
        self.actions.iocs = WindowAction(
            name="show_iocs_window_action",
            text="&IOCs",
            display_file=ui_dir / "iocs.py",
            WindowClass=FireflyMainWindow,
        )
        # Launch ion chamber voltmeters window
        self.actions.voltmeter = WindowAction(
            name="show_voltmeters_window_action",
            text="&Voltmeters",
            display_file=ui_dir / "voltmeters.py",
            WindowClass=FireflyMainWindow,
            shortcut="Ctrl+V",
            icon=qta.icon("ph.faders-horizontal"),
        )
        self.actions.voltmeter.window_created.connect(self.finalize_voltmeter_window)
        # Launch log window
        self.actions.log = WindowAction(
            name="show_logs_window_action",
            text="Logs",
            display_file=ui_dir / "log_viewer.ui",
            WindowClass=FireflyMainWindow,
            icon=qta.icon("mdi.view-list-outline"),
        )
        # Launch energy window
        self.actions.energy = WindowAction(
            name="show_energy_window_action",
            text="Energy",
            display_file=ui_dir / "energy.py",
            WindowClass=PlanMainWindow,
            shortcut="Ctrl+E",
            icon=qta.icon("mdi.sine-wave"),
        )

    @asyncSlot(QAction)
    async def finalize_new_window(self, action):
        """Slot for providing new windows for after a new window is created."""
        action.window.setup_menu_actions(actions=self.actions)
        self.queue_status_changed.connect(action.window.update_queue_status)
        self.queue_status_changed.connect(action.window.update_queue_controls)
        if getattr(self, "_queue_client", None) is not None:
            status = await self._queue_client.queue_status()
            action.window.update_queue_status(status)
            action.window.update_queue_controls(status)
        action.display.queue_item_submitted.connect(self.add_queue_item)
        # Send the current devices to the window
        await action.window.update_devices(self.registry)

    @asyncSlot(QAction)
    async def finalize_run_browser_window(self, action):
        """Connect up run browser signals and load initial data."""
        display = action.display
        self.run_updated.connect(display.update_running_scan)
        self.run_stopped.connect(display.update_running_scan)
        # Set initial state for the run_browser
        client = tiled_client(catalog=None)
        config = load_config()["tiled"]
        await display.setup_database(
            tiled_client=client, catalog_name=config["default_catalog"]
        )

    def finalize_status_window(self, action):
        """Connect up signals that are specific to the voltmeters window."""
        display = action.display
        display.ui.bss_modify_button.clicked.connect(self.actions.bss.trigger)
        # display.details_window_requested.connect

    def finalize_voltmeter_window(self, action):
        """Connect up signals that are specific to the voltmeters window."""

        def launch_ion_chamber_window(ic_name):
            action = self.actions.ion_chambers[ic_name]
            action.trigger()

        display = action.window.display_widget()
        display.details_window_requested.connect(launch_ion_chamber_window)

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

    def setup_queue_actions(self):
        """Create QAction objects for controlling the bluesky queueserver."""
        # Internal actions for interacting with the run engine
        self.check_queue_status_action = QtWidgets.QAction(self)
        # Action for launch queue-monitor
        self.actions.queue_monitor = Action(
            name="launch_queuemonitor_action",
            text="Queue Monitor",
            shortcut="Ctrl+Q",
        )
        self.actions.queue_monitor.triggered.connect(self.launch_queuemonitor)
        # Navbar actions for controlling the run engine
        self.actions.queue_controls = {
            "pause": Action(
                name="pause_runengine_action",
                text="Pause",
                shortcut="Ctrl+D",
                icon=qta.icon("fa5s.stopwatch"),
                tooltip="Pause the current plan at the next checkpoint.",
            ),
            "pause_now": Action(
                name="pause_runengine_now_action",
                text="Pause now",
                shortcut="Ctrl+C",
                icon=qta.icon("fa5s.pause"),
                tooltip="Pause the run engine now.",
            ),
            "resume": Action(
                name="resume_runengine_action",
                text="Resume",
                icon=qta.icon("fa5s.play"),
                tooltip="Resume a paused run engine at the last checkpoint.",
            ),
            "stop_runengine": Action(
                name="stop_runengine_action",
                text="Success",
                icon=qta.icon("fa5s.check"),
                tooltip="End the current plan, marking as successful.",
                checkable=True,
            ),
            "abort": Action(
                name="abort_runengine_action",
                text="Abort",
                icon=qta.icon("fa5s.times"),
                tooltip="End the current plan, marking as failure.",
            ),
            "start": Action(
                name="start_queue_action",
                text="Start",
                icon=qta.icon("fa5s.play"),
                tooltip="Start the queue",
            ),
            "halt": Action(
                name="halt_runengine_action",
                text="Halt",
                icon=qta.icon("fa5s.ban"),
                tooltip="End the current plan immediately, do not clean up.",
            ),
            "stop_queue": Action(
                name="stop_queue_action",
                text="Stop Queue",
                icon=qta.icon("fa5s.stop"),
                tooltip="Instruct the queue to stop after the current item is done.",
                checkable=True,
            ),
        }
        # Actions that control how the queue operates
        self.actions.queue_settings = {
            "autostart": Action(
                name="queue_autostart_action",
                text="&Autoplay",
                tooltip="If enabled, the queue will start when items are added.",
                checkable=True,
            ),
            "open_environment": Action(
                name="queue_open_environment_action",
                text="&Open Environment",
                tooltip="If open (checked), the queue server is able to run plans.",
                checkable=True,
            ),
        }

    def device_actions(
        self,
        device_label: str,
        display_file: str | None = None,
        device_key: str = "DEVICE",
        WindowClass: type = FireflyMainWindow,
        icon: QIcon = None,
    ):
        """Generic routine to be called for individual classes of devices.

        Sets up a window action for each instance of this device class
        (specified by *device_label*).

        For example, to set up device window actions for all a Tardis
        (Ophyd devices with the "tardis_ship" label), call:

        .. code:: python

            app.device_actions(device_label="tardis_ship")

        Parameters
        ==========
        device_label
          The Ophyd label by which to find the devices.
        display_file
          A path object pointing to the .ui or .py file to use for
          this device.
        device_key
          A key to use for the device name in the macros
          dictionary. If *device_key* is "DEVICE" (default), then the
          macros will be {"DEVICE": device.name}. Has no effect if
          *window_slot* is used.
        WindowClass
          The type of window to create around this device display.
        icon
          A QIcon that will be added to the action.

        """
        # We need a UI file, unless a custom window_slot is given
        # Get needed devices from the device registry
        try:
            devices = sorted(
                self.registry.findall(label=device_label), key=lambda x: x.name
            )
        except ComponentNotFound:
            log.warning(f"No {device_label} found, menu will be empty.")
            devices = []
        # Create menu actions for each device
        actions = {
            device.name: WindowAction(
                name=f"show_{device.name}_action",
                text=titleize(device.name),
                display_file=display_file,
                icon=icon,
                WindowClass=WindowClass,
                macros={device_key: device.name},
            )
            for device in devices
        }
        return actions

    def prepare_kafka_client(self):
        client = KafkaClient()
        self._kafka_client = client
        client.run_started.connect(self.run_started)
        client.run_updated.connect(self.run_updated)
        client.run_stopped.connect(self.run_stopped)

    def start_kafka_client(self):
        try:
            self._kafka_client.start()
        except Exception as exc:
            log.error(f"Could not start kafka client: {exc}")
        else:
            log.info("Started kafka client.")

    def start_queue_client(self):
        try:
            self._queue_client.start()
        except Exception as exc:
            log.error(f"Could not start queue client: {exc}")

    def prepare_queue_client(self, client=None, api=None):
        """Set up the QueueClient object that talks to the queue server.

        Parameters
        ==========
        api
          queueserver API. Used for testing.

        """
        # Load the API for controlling the queueserver.
        if api is None:
            try:
                api = queueserver_api()
            except InvalidConfiguration:
                log.error(
                    "Could not load queueserver API "
                    "configuration from iconfig.toml file."
                )
                return
        # Create the client object
        if client is None:
            client = QueueClient(api=api)
        # self.queue_open_environment_action.triggered.connect(client.open_environment)
        self.actions.queue_settings["open_environment"].triggered.connect(
            client.open_environment
        )
        self._queue_client = client
        # Connect actions to slots for controlling the queueserver
        self.actions.queue_controls["pause"].triggered.connect(
            partial(client.request_pause, defer=True)
        )
        self.actions.queue_controls["pause_now"].triggered.connect(
            partial(client.request_pause, defer=False)
        )
        self.actions.queue_controls["start"].triggered.connect(client.start_queue)
        self.actions.queue_controls["resume"].triggered.connect(client.resume_runengine)
        self.actions.queue_controls["stop_runengine"].triggered.connect(
            client.stop_runengine
        )
        self.actions.queue_controls["halt"].triggered.connect(client.halt_runengine)
        self.actions.queue_controls["abort"].triggered.connect(client.abort_runengine)
        self.actions.queue_controls["stop_queue"].triggered.connect(client.stop_queue)
        self.check_queue_status_action.triggered.connect(partial(client.update, True))
        # Connect signals/slots for queueserver state changes
        client.status_changed.connect(self.queue_status_changed)
        client.in_use_changed.connect(self.queue_in_use_changed)
        client.autostart_changed.connect(
            self.actions.queue_settings["autostart"].setChecked
        )
        client.environment_opened.connect(self.queue_environment_opened)
        client.environment_opened.connect(self.queue_environment_opened)
        self.queue_environment_opened.connect(self.set_open_environment_action_state)
        client.environment_state_changed.connect(self.queue_environment_state_changed)
        client.manager_state_changed.connect(self.queue_manager_state_changed)
        client.re_state_changed.connect(self.queue_re_state_changed)
        client.queue_stop_changed.connect(
            self.actions.queue_controls["stop_queue"].setChecked
        )
        client.devices_changed.connect(self.update_devices_allowed)
        self.actions.queue_settings["autostart"].toggled.connect(
            self.check_queue_status_action.trigger
        )
        self.actions.queue_settings["autostart"].toggled.connect(
            client.toggle_autostart
        )
        return client

    def start(self):
        """Start the background clients."""
        self.prepare_queue_client()
        self.prepare_kafka_client()
        self.start_queue_client()
        self.start_kafka_client()

    def update_devices_allowed(self, devices):
        pass

    @Slot(str)
    def enable_queue_controls(self, re_state):
        """Enable/disable the navbar buttons that control the queue.

        Most buttons are only relevant when the run engine is in
        certain states. For exmple, you can't click Play if the run
        engine is already running.

        """
        queue_actions = self.actions.queue_controls
        # Decide which signals to enable
        unknown_re_state = re_state is None or re_state.strip() == ""
        if unknown_re_state:
            # Unknown state, no button should work
            enabled_signals = []
        elif re_state == "idle":
            enabled_signals = [queue_actions["start"]]
        elif re_state == "paused":
            enabled_signals = [
                queue_actions["stop_runengine"],
                queue_actions["resume"],
                queue_actions["halt"],
                queue_actions["abort"],
            ]
        elif re_state == "running":
            enabled_signals = [
                queue_actions["pause"],
                queue_actions["pause_now"],
                queue_actions["stop_queue"],
            ]
        elif re_state in ["stopping", "aborting"]:
            enabled_signals = []
        else:
            enabled_signals = []
            raise ValueError(f"Unknown run engine state: {re_state}")
        # Enable/disable the relevant signals
        for action in queue_actions.values():
            action.setEnabled(action in enabled_signals)

    @asyncSlot(object)
    async def add_queue_item(self, item):
        log.debug(f"Application received item to add to queue: {item}")
        if getattr(self, "_queue_client", None) is not None:
            await self._queue_client.add_queue_item(item)

    @QtCore.Slot(bool)
    def set_open_environment_action_state(self, is_open: bool):
        """Update the readback value for opening the queueserver environment."""
        action = self.actions.queue_settings["open_environment"]
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
