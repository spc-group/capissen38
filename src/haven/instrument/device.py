import asyncio
import logging
import re
import time as ttime
from typing import Callable, Union

from caproto import CaprotoTimeoutError
from caproto.asyncio.client import Context
from ophyd import Component, Device, K
from ophyd.sim import make_fake_device

from .._iconfig import load_config

log = logging.getLogger(__name__)


async def resolve_device_names(ic_defns):
    """Update ion chamber definitions to include the EPICS name field.

    Updates *ic_defns* in place to add the *name* key. Each entry in
    *ic_defns* should have a *desc_pv* key with the PV to be checked
    for the device name.

    Ensures names are safe as Ophyd device names.

    """

    async def get_name(pv):
        try:
            response = await pv.read()
        except CaprotoTimeoutError:
            return None
        else:
            # Read PV values over the network
            return response.data.tobytes().strip(b"\x00").decode("latin-1")

    ctx = Context()
    desc_pvs = await ctx.get_pvs(*[defn["desc_pv"] for defn in ic_defns])
    names = await asyncio.gather(*(get_name(pv) for pv in desc_pvs))
    # Add the results back into the defitions
    for name, defn in zip(names, ic_defns):
        defn["name"] = name


def titelize(name):
    """Convert a device name into a human-readable title."""
    title = name.replace("_", " ").title()
    # Replace select phrases that are known to be incorrect
    replacements = {"Kb ": "KB "}
    for orig, new in replacements.items():
        title = title.replace(orig, new)
    return title


async def aload_devices(*coros):
    return await asyncio.gather(*coros)


def make_device(DeviceClass, *args, FakeDeviceClass=None, **kwargs) -> Device:
    """Create device and add it to the registry.

    If the beamline is not connected, i.e. the config file has:

        [beamline]
        is_connected = false

    then the created device will be simulated.

    Parameters
    ==========
    DeviceClass
      The device class to use for making this device.
    FakeDeviceClass
      If the beamline is not connected, use this device instead.

    Returns
    =======
    device
      The newly created and registered camera object.

    """
    # Make a fake device if the beamline is not connected
    config = load_config()
    if config["beamline"]["is_connected"]:
        Cls = DeviceClass
    else:
        # Make fake device
        if FakeDeviceClass is None:
            Cls = make_fake_device(DeviceClass)
        else:
            Cls = FakeDeviceClass
    # Make sure we can connect
    name = kwargs.get("name", "unknown")
    t0 = ttime.monotonic()
    device = Cls(
        *args,
        **kwargs,
    )
    return device


async def await_for_connection(dev, all_signals=False, timeout=3.0):
    """Wait for signals to connect

    Parameters
    ----------
    all_signals : bool, optional
        Wait for all signals to connect (including lazy ones)
    timeout : float or None
        Overall timeout
    """
    signals = [walk.item for walk in dev.walk_signals(include_lazy=all_signals)]

    pending_funcs = {
        dev: getattr(dev, "_required_for_connection", {})
        for name, dev in dev.walk_subdevices(include_lazy=all_signals)
    }
    pending_funcs[dev] = dev._required_for_connection

    t0 = ttime.monotonic()
    # Wait until all the signals have connected
    loop_idx = 0
    connected = False
    while True:
        # Check if the device is ready
        if not connected:
            connected = all(sig.connected for sig in signals)
        if connected and not any(pending_funcs.values()):
            return
        # Since we're not connected, sleep for a short time and try again
        real_timeout = min((0.05, timeout / 10.0))
        tn = ttime.monotonic()
        await asyncio.sleep(real_timeout)
        # Detect other co-routines blocking for too long
        tdelay = ttime.monotonic() - tn
        if tdelay > (real_timeout * 5):
            msg = f"{real_timeout} sec sleep for {dev.name} took "
            msg += f"{tdelay:.4f} sec. "
            msg += "Maybe another co-routine is blocking."
            log.info(msg)
        elapsed_time = ttime.monotonic() - t0
        loop_idx += 1
        if timeout is not None and elapsed_time > timeout and loop_idx > 2:
            break

    def get_name(sig):
        sig_name = f"{dev.name}.{sig.dotted_name}"
        return f"{sig_name} ({sig.pvname})" if hasattr(sig, "pvname") else sig_name

    reasons = []
    unconnected = ", ".join(get_name(sig) for sig in signals if not sig.connected)
    if unconnected:
        reasons.append(f"Failed to connect to all signals: {unconnected}")
    if any(pending_funcs.values()):
        pending = ", ".join(
            description.format(device=dev)
            for dev, funcs in pending_funcs.items()
            for obj, description in funcs.items()
        )
        reasons.append(f"Pending operations: {pending}")
    raise TimeoutError(dev.name + "; ".join(reasons))


class RegexComponent(Component[K]):
    r"""A component with regular expression matching.

    In EPICS, it is not possible to add a field to an existing record,
    e.g. adding a ``.RnXY`` field to go alongside ``mca1.RnNM`` and
    other fields in the MCA record. A common solution is to create a
    new record with an underscore instead of the dot: ``mca1_RnBH``.

    This component include these types of field-like-records as part
    of the ROI device with a ``mca1.Rn`` prefix but performing
    subsitution on the device name using regular expressions. See the
    documentation for ``re.sub`` for full details.

    Example
    =======

    .. code:: python

        class ROI(mca.ROI):
            name = RECpt(EpicsSignal, "NM", lazy=True)
            is_hinted = RECpt(EpicsSignal, "BH",
                              pattern=r"^(.+)\.R(\d+)",
                              repl=r"\1_R\2",
                              lazy=True)

        class MCA(mca.EpicsMCARecord):
            roi0 = Cpt(ROI, ".R0")
            roi1 = Cpt(ROI, ".R1")

        mca = MCA(prefix="mca")
        # *name* has the normal concatination
        assert mca.roi0.name.pvname == "mca.R0NM"
        # *is_hinted* has regex substitution
        assert mca.roi0.is_hinted.pvname == "mca_R0BH"

    """

    def __init__(self, *args, pattern: str, repl: Union[str, Callable], **kwargs):
        """*pattern* and *repl* match their use in ``re.sub``."""
        self.pattern = pattern
        self.repl = repl
        super().__init__(*args, **kwargs)

    def maybe_add_prefix(self, instance, kw, suffix):
        """Parse prefix and suffix with regex suffix if kw is in self.add_prefix.

        Parameters
        ----------
        instance : Device
            The instance from which to extract the prefix to maybe
            append to the suffix.

        kw : str
            The key of associated with the suffix.  If this key is
            self.add_prefix than prepend the prefix to the suffix and
            return, else just return the suffix.

        suffix : str
            The suffix to maybe have something prepended to.

        Returns
        -------
        str

        """
        new_val = super().maybe_add_prefix(instance, kw, suffix)
        try:
            new_val = re.sub(self.pattern, self.repl, new_val)
        except TypeError:
            pass
        return new_val


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
