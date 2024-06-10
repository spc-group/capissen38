import re  # noqa: F401

import databroker  # noqa: F401
from bluesky.plan_stubs import (  # noqa: F401
    abs_set,
    mv,
    mvr,
    null,
    pause,
    rel_set,
    sleep,
    stop,
)
from bluesky.plans import (  # noqa: F401
    count,
    grid_scan,
    list_scan,
    rel_grid_scan,
    rel_list_scan,
    rel_scan,
    scan,
    scan_nd,
)

# Import plans
from haven import registry  # noqa: F401
from haven import (  # noqa: F401
    align_pitch2,
    align_slits,
    auto_gain,
    calibrate_mono_gap,
    energy_scan,
    knife_scan,
    recall_motor_position,
    set_energy,
    xafs_scan,
)
from haven.instrument.load_instrument import (  # noqa: F401
    load_instrument,
    load_simulated_devices,
)
from haven.run_engine import run_engine  # noqa: F401

# Import devices
load_instrument()
load_simulated_devices()
for cpt in registry._objects_by_name.values():
    # Replace spaces and other illegal characters in variable name
    # name = re.sub('\W|^(?=\d)','_', cpt.name)
    # Add the device as a variable in module's globals
    globals()[cpt.name] = cpt

# Create a run engine without all the bells and whistles
RE = run_engine(connect_databroker=False, use_bec=False)
