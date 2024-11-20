"""More calculations from Yanna.

def theta_bragg(energy_val, hkl=[4,4,4]):
    d_spacing = lattice_cons / np.sqrt(hkl[0] ** 2 + hkl[1] ** 2 + hkl[2] ** 2)
    theta_bragg_val = np.arcsin(hc / (energy_val * 2 * d_spacing))
    theta_bragg_val = np.degrees(theta_bragg_val)
    return theta_bragg_val


Some sane values for converting hkl and [HKL] to α:

(001), (101), 90°
(001), (110), 180°

"""

import asyncio
import logging

import numpy as np
from bluesky.protocols import Movable
from ophyd import Component as Cpt
from ophyd import Device, EpicsMotor
from ophyd import FormattedComponent as FCpt
from ophyd import PseudoPositioner, PseudoSingle, Signal
from ophyd.pseudopos import pseudo_position_argument, real_position_argument
from ophyd_async.core import (
    AsyncStatus,
    ConfigSignal,
    Device,
    StandardReadable,
    soft_signal_r_and_setter,
    soft_signal_rw,
)
from scipy import constants

from ..positioner import Positioner
from .motor import Motor
from .signal import derived_signal_r, derived_signal_rw

log = logging.getLogger(__name__)

um_per_mm = 1000


h = constants.physical_constants["Planck constant in eV/Hz"][0]
c = constants.c


def energy_to_wavelength(energy):
    """Energy in eV to wavelength in meters."""
    return h * c / energy


wavelength_to_energy = energy_to_wavelength


def bragg_to_wavelength(bragg_angle: float, d: float, n: int = 1):
    """Convert Bragg angle to wavelength.

    Parameters
    ==========
    bragg_angle
      The Bragg angle (θ) of the reflection.
    d
      Inter-planar spacing of the crystal.
    n
      The order of the reflection.
    """
    return 2 * d * np.sin(bragg_angle) / n


def wavelength_to_bragg(wavelength: float, d: float, n: int = 1):
    """Convert wavelength to Bragg angle.

    Parameters
    ==========
    wavelength
      The photon wavelength in meters.
    d
      Inter-planar spacing of the crystal.
    n
      The order of the reflection.

    Returns
    =======
    bragg
      The Bragg angle of the reflection, in Radians.
    """
    return np.arcsin(n * wavelength / 2 / d)


def energy_to_bragg(energy: float, d: float) -> float:
    """Convert photon energy to Bragg angle.

    Parameters
    ==========
    energy
      Photon energy, in eV.
    d
      d-spacing of the analyzer crystal, in meters.

    Returns
    =======
    bragg
      First order Bragg angle for this photon, in radians.

    """
    bragg = np.arcsin(h * c / 2 / d / energy)
    return bragg


def bragg_to_energy(bragg: float, d: float) -> float:
    """Convert Bragg angle to photon energy.

    Parameters
    ==========
    bragg
      Bragg angle for the crystal, in radians.
    d
      d-spacing of the analyzer crystal, in meters.

    Returns
    =======
    energy
      Photon energy, in eV.

    """
    energy = h * c / 2 / d / np.sin(bragg)
    return energy


def hkl_to_alpha(base, reflection):
    cos_alpha = (
        np.dot(base, reflection) / np.linalg.norm(base) / np.linalg.norm(reflection)
    )
    if cos_alpha > 1:
        cos_alpha = 1
    alpha = np.arccos(cos_alpha)
    return alpha


class HKL(StandardReadable, Movable):
    """A set of (h, k, l) for a lattice plane.

    Settable as ``hkl.set('312')``, which will set ``hkl.h``,
    ``hkl.k``, and ``hkl.l``.

    """

    def __init__(self, initial_value, name=""):
        h, k, l = self._to_tuple(initial_value)
        self.h = soft_signal_rw(int, initial_value=h)
        self.k = soft_signal_rw(int, initial_value=k)
        self.l = soft_signal_rw(int, initial_value=l)

        super().__init__(name=name)

    def _to_tuple(self, hkl_str):
        h, k, l = hkl_str
        return (h, k, l)

    @AsyncStatus.wrap
    async def set(self, value):
        h, k, l = self._to_tuple(value)
        await asyncio.gather(
            self.h.set(h),
            self.k.set(k),
            self.l.set(l),
        )


class Analyzer(StandardReadable):
    """A single asymmetric analyzer crystal mounted on an Rowland circle.

    Linear dimensions (e.g. Rowland diameter) should be in units that
    match those of the real motors. Angles are in radians.

    """

    linear_units = "mm"
    angular_units = "rad"

    def __init__(
        self,
        *,
        horizontal_motor_prefix: str,
        vertical_motor_prefix: str,
        yaw_motor_prefix: str,
        rowland_diameter: float | int = 500000,  # µm
        lattice_constant: float = 0.543095e-9,  # m
        wedge_angle: float = np.radians(30),
        surface_plane: tuple[int, int, int] | str = "211",
        name: str = "",
    ):
        surface_plane = tuple(int(i) for i in surface_plane)
        # Create the real motors
        self.horizontal = Motor(horizontal_motor_prefix)
        self.vertical = Motor(vertical_motor_prefix)
        self.crystal_yaw = Motor(yaw_motor_prefix)
        # Reciprocal space geometry
        self.reflection = HKL(initial_value="111")
        self.surface_plane = HKL(initial_value=surface_plane)
        self.add_readables(
            [
                self.reflection.h,
                self.reflection.k,
                self.reflection.l,
                self.surface_plane.h,
                self.surface_plane.k,
                self.surface_plane.l,
            ],
            ConfigSignal,
        )
        # Soft signals for keeping track of the fixed transform properties
        with self.add_children_as_readables(ConfigSignal):
            self.rowland_diameter = soft_signal_rw(
                float, units=self.linear_units, initial_value=rowland_diameter
            )
            self.wedge_angle = soft_signal_rw(
                float, units=self.angular_units, initial_value=wedge_angle
            )
            self.lattice_constant = soft_signal_rw(
                float, units=self.linear_units, initial_value=lattice_constant
            )
            self.bragg_offset = soft_signal_rw(float, units=self.linear_units)
            # Soft signals for intermediate, calculated values
            self.d_spacing = derived_signal_r(
                float,
                derived_from={
                    "H": self.reflection.h,
                    "K": self.reflection.k,
                    "L": self.reflection.l,
                    "a": self.lattice_constant,
                },
                inverse=self._calc_d_spacing,
                units=self.linear_units,
                precision=4,
            )
            self.asymmetry_angle = derived_signal_r(
                float,
                derived_from={
                    "H": self.reflection.h,
                    "K": self.reflection.k,
                    "L": self.reflection.l,
                    "h": self.surface_plane.h,
                    "k": self.surface_plane.k,
                    "l": self.surface_plane.l,
                },
                units=self.angular_units,
                inverse=self._calc_alpha,
            )
        # The actual energy signal that controls the analyzer
        self.energy = EnergyPositioner(xtal=self)
        # Decide which signals should be readable/config/etc
        self.add_readables(
            [
                self.energy.readback,
                self.energy.setpoint,
                self.vertical.user_readback,
                self.horizontal.user_readback,
            ]
        )
        self.add_readables(
            [
                self.crystal_yaw.user_readback,
            ],
            ConfigSignal,
        )
        super().__init__(name=name)

    def _calc_alpha(self, values, H, K, L, h, k, l):
        """Calculate the asymmetry angle for a given reflection and base plane.

        Parameters
        ==========
        H, K, L
          The specific reflection plane to use.
        h, k, l
          The base cut of the crystal surface.

        """
        base = (values[h], values[k], values[l])
        refl = (values[H], values[K], values[L])
        return hkl_to_alpha(base=base, reflection=refl)

    def _calc_d_spacing(self, values, H, K, L, a):
        hkl = (values[H], values[K], values[L])
        return values[a] / np.linalg.norm(hkl)


class EnergyPositioner(Positioner):
    """Positions the energy of an analyzer crystal."""

    def __init__(self, *, xtal: Analyzer, name: str = ""):
        xtal_signals = {
            "D": xtal.rowland_diameter,
            "d": xtal.d_spacing,
            "beta": xtal.wedge_angle,
            "alpha": xtal.asymmetry_angle,
        }
        self.setpoint = derived_signal_rw(
            float,
            units="eV",
            derived_from=dict(
                x=xtal.horizontal.user_setpoint,
                y=xtal.vertical.user_setpoint,
                **xtal_signals,
            ),
            forward=self.forward,
            inverse=self.inverse,
        )
        with self.add_children_as_readables():
            self.readback = derived_signal_r(
                float,
                units="eV",
                derived_from=dict(
                    x=xtal.horizontal.user_readback,
                    y=xtal.vertical.user_readback,
                    **xtal_signals,
                ),
                inverse=self.inverse,
            )
        # Metadata
        self.velocity, _ = soft_signal_r_and_setter(float, initial_value=0.001)
        self.units, _ = soft_signal_r_and_setter(str, initial_value="eV")
        self.precision, _ = soft_signal_r_and_setter(int, initial_value=3)
        super().__init__(name=name, put_complete=True)

    async def forward(self, value, D, d, beta, alpha, x, y):
        """Run a forward (pseudo -> real) calculation"""
        # Resolve the dependent signals into their values
        energy = value
        D, d, beta, alpha = await asyncio.gather(
            D.get_value(),
            d.get_value(),
            beta.get_value(),
            alpha.get_value(),
        )
        # Step 0: convert energy to bragg angle
        bragg = energy_to_bragg(energy, d=d)
        # Step 1: Convert energy params to geometry params
        theta_M = bragg + alpha
        rho = D * np.sin(theta_M)
        # Step 2: Convert geometry params to motor positions
        y_val = rho * np.cos(theta_M) / np.cos(beta)
        x_val = -y_val * np.sin(beta) + rho * np.sin(theta_M)
        # Report the calculated result
        return {
            x: x_val,
            y: y_val,
        }

    def inverse(self, values, D, d, beta, alpha, x, y):
        """Run an inverse (real -> pseudo) calculation"""
        # Resolve signals into their values
        x = values[x]
        y = values[y]
        D = values[D]
        d = values[d]
        beta = values[beta]
        alpha = values[alpha]
        # Step 1: Convert motor positions to geometry parameters
        theta_M = np.arctan2((x + y * np.sin(beta)), (y * np.cos(beta)))
        rho = y * np.cos(beta) / np.cos(theta_M)
        # Step 1: Convert geometry params to energy
        bragg = theta_M - alpha
        energy = bragg_to_energy(bragg, d=d)
        return energy


class Asymmotron(StandardReadable):
    pass


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
