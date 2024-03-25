import time
import logging
import databroker  # noqa: F401
import matplotlib.pyplot as plt  # noqa: F401
from bluesky import RunEngine  # noqa: F401
from bluesky import plan_stubs as bps  # noqa: F401
from bluesky import plans as bp  # noqa: F401
from bluesky import suspenders  # noqa: F401
from bluesky.callbacks.best_effort import BestEffortCallback  # noqa: F401
from bluesky.simulators import summarize_plan  # noqa: F401

import haven  # noqa: F401

logging.basicConfig(level=logging.WARNING)

# Allow best effort callback to update properly
plt.ion()

# Prepare the haven instrument
config = haven.load_config()
t0 = time.monotonic()
print(f"Initializing {config['beamline']['name']}…")
haven.load_instrument()
print(f"Finished initalization in {time.monotonic() - t0:.2f} seconds.")
RE = haven.run_engine()
ion_chambers = haven.registry.findall("ion_chambers")

# Add metadata to the run engine
RE.preprocessors.append(haven.preprocessors.inject_haven_md_wrapper)
