import logging
import warnings
from typing import Optional, Sequence

import pandas as pd
from bluesky.callbacks.best_effort import BestEffortCallback
from lmfit.model import Model
from lmfit.models import QuadraticModel

from haven.typing import Motor

from ..instrument.instrument_registry import registry
from .align_motor import align_motor, align_pitch2
from .set_energy import set_energy

__all__ = ["mono_ID_calibration"]


log = logging.getLogger(__name__)


def mono_ID_calibration(
    energies: Sequence,
    mono_motor: Motor = "energy_mono_energy",
    id_motor: Motor = "energy_id_energy",
    energy_motor: Motor = "energy",
    detector="I0",
    fit_model: Optional[Model] = None,
):
    """A bluesky plan to measure the offset between monochromator and
    insertion device energies.

    This plan will print the results of the equation. The fit results
    will also be added to the *fit_model* object as
    `fit_model.result`.

    Pseudo-code:

    - for energy in *energies*

      - Move ID to *energy*
      - Align pitch motor
      - 1D scan over mono energy motor
      - Calculate mono energy motor position for maximum flux

    - Fit ID energy vs mono energy with function

    Parameters
    ==========
    energies
      The target energies, in eV, over which the calibration will be
      performed.
    mono_motor
      The motor to move for monochromator energy (will be scanned).
    id_motor
      The motor to move for the insertion device (will not be
      scanned).
    energy_motor
      The motor to move when initially setting the energy for each
      point.
    detector
      The detector to measure.
    fit_model
      A lmfit model object that with determine the final fitting
      parameters for the calibration curve.

    """
    # Resolve device names
    mono_motor = registry.find(mono_motor)
    id_motor = registry.find(id_motor)
    results_df = pd.DataFrame(columns=["id_energy", "mono_energy"])
    # Do each energy point
    for energy in energies:
        # Set the mono and ID to the target energy to get started
        yield from set_energy(energy, positioners=[energy_motor])
        # Align the pitch motor
        yield from align_pitch2(detector=detector)
        # Determine maximum mono energy
        bec = BestEffortCallback()
        bec.disable_plots()
        bec.disable_table()
        detector_ = registry.find(detector)
        yield from align_motor(
            motor=id_motor, detector=detector_, distance=0.4, bec=bec
        )
        # Save the results to the dataframe for fitting later
        peak_center = bec.peaks["cen"]
        signal_name = getattr(detector_, "raw_counts", detector_).name
        try:
            mono_energy = mono_motor.user_readback.get()
        except AttributeError:
            mono_energy = mono_motor.readback.get()
        if signal_name in peak_center.keys():
            # results_df = results_df.append(
            new_row = {
                "id_energy": bec.peaks["cen"][signal_name],
                "mono_energy": mono_energy,
            }
            results_df = pd.concat(
                [results_df, pd.DataFrame([new_row])], ignore_index=True
            )
    # Fit the overall mono-ID calibration curve
    if fit_model is None:
        fit_model = QuadraticModel(nan_policy="omit")
    y = results_df.id_energy
    x = results_df.mono_energy
    params = fit_model.guess(y, x=x)
    try:
        fit = fit_model.fit(y, params, x=x)
    except Exception as e:
        log.warning(str(e))
        warnings.warn(str(e))
    else:
        fit_model.fit_result = fit
    fit_model.results_df = results_df


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
