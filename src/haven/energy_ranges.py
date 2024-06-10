import math
from dataclasses import dataclass

import numpy as np
import pint
from scipy import constants

__all__ = ["ERange", "KRange"]


DEFAULT_EXPOSURE = 0.5

# Calculate the conversion coefficient from k -> eV
ureg = pint.UnitRegistry()
hbar = constants.hbar * ureg.joule * ureg.second
c = constants.speed_of_light * ureg.meter / ureg.second
m_e = (
    constants.physical_constants["electron mass energy equivalent in MeV"][0]
    * 1e6
    * ureg.electron_volt
)
ALPHA = hbar**2 * c**2 / 2 / m_e
ALPHA = ALPHA.to("electron_volt * angstrom * angstrom").magnitude


def energy_to_wavenumber(energy):
    return np.sqrt(energy / ALPHA)


def wavenumber_to_energy(wavenumber):
    return wavenumber**2 * ALPHA


# converting between energy steps and k steps
def E_step_to_k_step(E_start, E_step):
    k0 = energy_to_wavenumber(E_start)
    k1 = energy_to_wavenumber(E_start + E_step)
    return k1 - k0


def k_step_to_E_step(k_start, k_step):
    E0 = wavenumber_to_energy(k_start)
    E1 = wavenumber_to_energy(k_start + k_step)
    return E1 - E0


def round_to_int(num):
    digits = -int(math.log10(math.ulp(num)))
    return int(round(num, digits))


@dataclass
class EnergyRange:
    """A range of energies used for scanning."""

    def energies(self):
        raise NotImplementedError

    def exposures(self):
        raise NotImplementedError


def full_range(start, end, step):
    """Calculate a range, but inclusive of start and end (if a multiple of
    the step).

    """

    num_steps = round_to_int((end - start) / step)
    lin_max = start + num_steps * step
    return np.linspace(start, lin_max, num=num_steps + 1)


@dataclass
class ERange(EnergyRange):
    """A range of energies used for scanning.

    All values are assumed to be in electron-volts. If *E0* is a

    Parameters
    ==========

    E_min
      Starting energy of the range, in eV.
    E_max
      Ending energy of the range, in eV.
    E_step
      Step-size between energies, in eV.
    weight
      Weighting factor for longer exposures at higher energies.
    exposure
      How long to spend at each energy, in seconds.

    """

    E_min: float
    E_max: float
    E_step: float = 1.0
    weight: float = 0.0
    exposure: float = DEFAULT_EXPOSURE

    def energies(self):
        """Convert the range to a sequence of actual energy values, in eV."""
        return full_range(self.E_min, self.E_max, self.E_step)

    def exposures(self):
        """Convert the range to a sequence of exposure times, in seconds."""
        # disable weight for now
        # return self.exposure  * self.energies() ** self.weight
        return self.exposure * self.energies() ** 0  # do not consider weights for now


@dataclass
class KRange(EnergyRange):
    """A range of energies used for scanning in the EXAFS region.

    Values are a mix of electron-volts and K-space values.

    Parameters
    ==========

    k_min
      Starting energy of the range, in eV.
    k_max
      Ending energy of the range, in Å⁻.
    k_step
      Step-size between energies, in Å⁻.
    k_weight
      Weighting factor for longer exposures at higher energies.
    exposure
      How long to spend at each energy, in seconds.

    """

    k_min: float
    k_max: float
    k_step: float = 0.1
    k_weight: float = 0.0
    exposure: float = DEFAULT_EXPOSURE

    def energies(self):
        """Calculates photon energies in units of eV."""
        return wavenumber_to_energy(self.wavenumbers())

    def wavenumbers(self):
        """Calculates wavenumbers (k) for the photo-electron in units Å⁻."""
        ks = full_range(self.k_min, self.k_max, self.k_step)
        return ks

    def exposures(self):
        ks = self.wavenumbers()
        return self.exposure * ((ks / np.min(ks)) ** self.k_weight)


def merge_ranges(*ranges, default_exposure=DEFAULT_EXPOSURE, sort=False):
    """Combine multiple energy ranges.

    If any of *ranges* is a instance of ``EnergyRange`` or one of its
    subclasses, then the object will be decomposed to it's constituent
    energies and exposure times. Otherwise, the value will be used
    as-is for the list of energies, and *default_exposure* will be
    used for the exposure time.

    Results will be sorted by energy, and redundant energies will be
    removed with the exposure time being taken from the first instance
    of the particular energy encountered.

    Returns
    =======
    energies
      A sequence of energies, in eV.
    exposures
      A sequence of exposure times, in seconds.

    """
    energies = []
    exposures = []
    for rng in ranges:
        if not isinstance(rng, EnergyRange):
            # Not an energy range, assume it's a float or something
            energies.append(rng)
            exposures.append(default_exposure)
        else:
            # An energy range, so break it down
            energies.extend(rng.energies())
            exposures.extend(rng.exposures())
    # Convert to proper arrays, and remove duplicate energies
    energies, unique_idx = np.unique(
        np.asarray(energies, dtype=float), return_index=True
    )
    exposures = np.asarray(exposures, dtype=float)[unique_idx]

    if sort:
        # sorting energies from small to big
        sorted_indices = np.argsort(energies)
        energies = energies[sorted_indices]
        exposures = exposures[sorted_indices]

    return energies, exposures


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
