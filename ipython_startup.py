import logging
import time
import asyncio

import databroker  # noqa: F401
import matplotlib.pyplot as plt  # noqa: F401
from bluesky import RunEngine  # noqa: F401
from bluesky import suspenders  # noqa: F401
from bluesky import plan_stubs as bps  # noqa: F401
from bluesky.plan_stubs import mv, mvr, rd  # noqa: F401
from bluesky import plans as bp  # noqa: F401
from bluesky.callbacks.best_effort import BestEffortCallback  # noqa: F401
from bluesky.simulators import summarize_plan  # noqa: F401
from ophyd_async.core import DeviceCollector

import haven  # noqa: F401

logging.basicConfig(level=logging.WARNING)


# Allow best effort callback to update properly
plt.ion()

# Prepare the haven instrument
config = haven.load_config()
# t0 = time.monotonic()
# print(f"Initializing {config['beamline']['name']}…")
# haven.load_instrument()
# print(f"Finished initalization in {time.monotonic() - t0:.2f} seconds.")

# Make sure asyncio and the bluesky run engine share an event loop
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
RE = haven.run_engine(loop=loop)

# Save references to some commonly used things in the global namespace
registry = haven.registry
ion_chambers = haven.registry.findall("ion_chambers", allow_none=True)

# Add metadata to the run engine
RE.preprocessors.append(haven.preprocessors.inject_haven_md_wrapper)
