import pydm
from ophyd import Signal
from pydm.data_plugins import plugin_for_address
from pydm.widgets import PyDMLineEdit

from firefly.pydm_plugin import HavenPlugin


def test_plugin_registered(ffapp):
    assert "haven" in ffapp.plugins.keys()
    plugin = plugin_for_address("haven://")
    assert isinstance(plugin, HavenPlugin)


def test_signal_connection(qapp, qtbot, sim_registry):
    # Create a signal and attach our listener
    sig = Signal(name="my_signal", value=1)
    widget = PyDMLineEdit()
    qtbot.addWidget(widget)
    widget.channel = "haven://my_signal"
    listener = widget.channels()[0]
    # If PyDMChannel can not connect, we need to connect it ourselves
    # In PyDM > 1.5.0 this will not be neccesary as the widget will be
    # connected after we set the channel name
    if not hasattr(listener, "connect"):
        pydm.utilities.establish_widget_connections(widget)
    # Check that our widget receives the initial value
    qapp.processEvents()
    # breakpoint()
    assert widget._write_access
    assert widget._connected
    assert widget.value == 1
