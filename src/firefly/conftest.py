import asyncio
import subprocess

import psutil
import pydm
import pytest
from qasync import DefaultQEventLoopPolicy, QEventLoop

from firefly import FireflyApplication
from firefly.main_window import FireflyMainWindow


@pytest.fixture(scope="session")
def qapp_cls():
    return FireflyApplication


# def pytest_configure(config):
#     app = qt_api.QtWidgets.QApplication.instance()
#     assert app is None
#     app = FireflyApplication()
#     app = qt_api.QtWidgets.QApplication.instance()
#     assert isinstance(app, FireflyApplication)
#     # # Create event loop for asyncio stuff
#     # loop = asyncio.new_event_loop()
#     # asyncio.set_event_loop(loop)


def tiled_is_running(port, match_command=True):
    lsof = subprocess.run(["lsof", "-i", f":{port}", "-F"], capture_output=True)
    assert lsof.stderr.decode() == ""
    stdout = lsof.stdout.decode().split("\n")
    is_running = len(stdout) >= 3
    if match_command:
        is_running = is_running and stdout[3] == "ctiled"
    return is_running


def kill_process(process_name):
    processes = []
    for proc in psutil.process_iter():
        # check whether the process name matches
        if proc.name() == process_name:
            proc.kill()
            processes.append(proc)
    # Wait for them all the terminate
    [proc.wait(timeout=5) for proc in processes]


@pytest.fixture(scope="session")
def pydm_ophyd_plugin():
    return pydm.data_plugins.plugin_for_address("haven://")


qs_status = {
    "msg": "RE Manager v0.0.18",
    "items_in_queue": 0,
    "items_in_history": 0,
    "running_item_uid": None,
    "manager_state": "idle",
    "queue_stop_pending": False,
    "worker_environment_exists": False,
    "worker_environment_state": "closed",
    "worker_background_tasks": 0,
    "re_state": None,
    "pause_pending": False,
    "run_list_uid": "4f2d48cc-980d-4472-b62b-6686caeb3833",
    "plan_queue_uid": "2b99ccd8-f69b-4a44-82d0-947d32c5d0a2",
    "plan_history_uid": "9af8e898-0f00-4e7a-8d97-0964c8d43f47",
    "devices_existing_uid": "51d8b88d-7457-42c4-b67f-097b168be96d",
    "plans_existing_uid": "65f11f60-0049-46f5-9eb3-9f1589c4a6dd",
    "devices_allowed_uid": "a5ddff29-917c-462e-ba66-399777d2442a",
    "plans_allowed_uid": "d1e907cd-cb92-4d68-baab-fe195754827e",
    "plan_queue_mode": {"loop": False},
    "task_results_uid": "159e1820-32be-4e01-ab03-e3478d12d288",
    "lock_info_uid": "c7fe6f73-91fc-457d-8db0-dfcecb2f2aba",
    "lock": {"environment": False, "queue": False},
}


class FireflyQEventLoopPolicy(DefaultQEventLoopPolicy):
    def new_event_loop(self):
        return QEventLoop(FireflyApplication.instance())


@pytest.fixture()
def event_loop_policy(request, ffapp):
    """Make sure pytest-asyncio uses the QEventLoop."""
    return FireflyQEventLoopPolicy()


@pytest.fixture()
def ffapp(pydm_ophyd_plugin, qapp_cls, qapp_args, pytestconfig):
    # Get an instance of the application
    # app = qt_api.QtWidgets.QApplication.instance()
    app = qapp_cls.instance()
    if app is None:
        # New Application
        global _ffapp_instance
        app = qapp_cls(*qapp_args)
        # _ffapp_instance = app
        name = pytestconfig.getini("qt_qapp_name")
        app.setApplicationName(name)
    # Make sure there's at least one Window, otherwise things get weird
    if getattr(app, "_dummy_main_window", None) is None:
        # Set up the actions and other boildplate stuff
        app.setup_window_actions()
        app.setup_runengine_actions()
        app._dummy_main_window = FireflyMainWindow()
    yield app
    # Delete any windows that might have been created
    for wndw in app.windows.values():
        wndw.close()


@pytest.fixture()
def affapp(event_loop, ffapp):
    # Prepare the event loop
    asyncio.set_event_loop(event_loop)
    # Sanity check to make sure a QApplication was not created by mistake
    assert isinstance(ffapp, FireflyApplication)
    # Yield the finalized application object
    try:
        yield ffapp
    finally:
        # Cancel remaining async tasks
        pending = asyncio.all_tasks(event_loop)
        event_loop.run_until_complete(asyncio.gather(*pending))
        assert all(task.done() for task in pending), "Shutdown tasks not complete."
        # if hasattr(app, "_queue_thread"):
        #     app._queue_thread.quit()
        #     app._queue_thread.wait(msecs=5000)
        # del app
        # gc.collect()
