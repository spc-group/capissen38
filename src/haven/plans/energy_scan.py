"""A bluesky plan to scan the X-ray energy and capture detector signals.

"""

import logging
from collections import ChainMap
from typing import Mapping, Optional, Sequence, Union

import numpy as np
from bluesky import plans as bp
from bluesky.preprocessors import subs_decorator

from .._iconfig import load_config
from ..constants import edge_energy
from ..instrument import registry
from ..preprocessors import baseline_decorator
from ..typing import DetectorList
from ..xdi_writer import XDIWriter

__all__ = ["energy_scan"]


log = logging.getLogger(__name__)


# @shutter_suspend_decorator()
@subs_decorator(
    XDIWriter("{manager_path}/{year}{month}{day}-{sample_name}-{edge}-{short_uid}.xdi")
)
@baseline_decorator()
def energy_scan(
    energies: Sequence[float],
    exposure: Union[float, Sequence[float]] = 0.1,
    E0: Union[float, str] = 0,
    detectors: DetectorList = "ion_chambers",
    energy_signals: Sequence = ["energy"],
    time_signals: Optional[Sequence] = None,
    md: Mapping = {},
):
    """Collect a spectrum by scanning X-ray energy.

    For scanning over a pre-defined X-ray absorption edge, try
    :py:func:`~haven.plans.xafs_scan.xafs_scan` instead.

    *exposure* can be either a float, or a sequence of floats. If a
    single value is provided, it will be used for all energies. If a
    sequence is provided, it should be the same length as *energies*
    and the each entry will be used for the corresponding entry in
    *energies*.

    The calculated exposure times will be set for every signal in
    *time_signals*. If *time_signals* is ``None``, then
    *time_signals* will be determined automatically from
    *detectors*: for each detector, if it has an attribute/property
    *default_time_signal*, then this signal will be included in
    *time_signals*.

    **Usage:**

    The following code will run a scan with 1 eV steps from 13000 to
    13099 eV.

        energies = range(13000, 13100)
        RE(energy_scan(energies, exposure=0.5))

    The preparation of energies is up to the calling function. For
    more sophisticated energy lists, consider using the utility
    functions :py:class:`haven.energy_ranges.ERange` and
    :py:class:`haven.energy_ranges.KRange`:

    .. code-block:: python

        energies = [
          ERange(13000, 13100, E_step=10),
          ERange(13100, 13160, E_step=0.5),
          KRange(13160, k_max=8, k_step=0.2),
        ]
        RE(energy_scan(energies, exposure=0.5))

    The results can also be viewed by passing
    :py:class:`haven.callbacks.live_xafs_plot.LiveXAFSPlot` to the RunEngine:

    .. code-block:: python

        RE(energy_scan(...), LiveXAFSPlot())

    Parameters
    ==========
    energies
      The X-ray energies, in eV, over which to scan.
    exposure
      How long, in seconds, to count at each energy.
    E0
      An edge energy, in eV, or name of the edge of the form
      ``"Ni_L3"``. All energies will be relative to this value.
    detectors
      The detectors to collect X-ray signal from at each energy.
    energy_signals
      Positioners that will receive the changing energies.
    time_signals
      Positioners that will receive the exposure time for each scan.
    md
      Additional metadata to pass on the to run engine.

    Yields
    ======
    Bluesky messages to execute the scan.

    """
    # Check that arguments are sensible
    if len(energy_signals) < 1:
        msg = "Cannot run energy_scan with empty *energy_signals*."
        log.error(msg)
        raise ValueError(msg)
    # Resolve the detector and positioner list if given by name
    if isinstance(detectors, str):
        detectors = registry.findall(detectors)
    real_detectors = []
    for det in detectors:
        real_detectors.extend(registry.findall(det))
    log.debug(f"Found registered detectors: {real_detectors}")
    energy_signals = [registry.find(ep) for ep in energy_signals]
    # Figure out which time positioners to use
    if time_signals is None:
        time_signals = [
            det.default_time_signal
            for det in detectors
            if hasattr(det, "default_time_signal")
        ]
    else:
        time_signals = [registry.find(tp) for tp in time_signals]
    # Convert an individual exposure time to an array of exposure times
    if not hasattr(exposure, "__iter__"):
        exposure = [exposure] * len(energies)
    # Correct for E0
    if isinstance(E0, str):
        # Look up E0 in the database if e.g. "Ni_K" is given as E0
        E0_str = E0
        E0 = edge_energy(E0)
    else:
        E0_str = None
    energies = np.asarray(energies)
    energies += E0
    # Todo: sort the energies and exposure times by the energy
    # Prepare the positioners list with associated energies and exposures
    scan_args = [(motor, energies) for motor in energy_signals]
    scan_args += [(motor, exposure) for motor in time_signals]
    scan_args = [item for items in scan_args for item in items]
    # Add some extra metadata
    config = load_config()
    md_ = {"edge": E0_str, "E0": E0}
    for signals in energy_signals:
        try:
            md_["d_spacing"] = signals.d_spacing.get()
        except AttributeError:
            continue
        else:
            break
    # Do the actual scan
    yield from bp.list_scan(
        real_detectors,
        *scan_args,
        md=ChainMap(md, md_, config),
    )


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
