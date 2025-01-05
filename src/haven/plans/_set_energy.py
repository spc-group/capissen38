from typing import Union

from bluesky import plan_stubs as bps

from .. import exceptions
from ..instrument import beamline
from ..typing import DetectorList

__all__ = ["set_energy"]


Harmonic = Union[str, int, None]


def auto_harmonic(energy: float, harmonic: Harmonic) -> Harmonic:
    # No harmonic change is requested
    if harmonic is None:
        return harmonic
    # Check for specific harmonics
    try:
        return int(harmonic)
    except ValueError:
        pass
    # Check for auto harmonic selection
    threshold = 11000
    if harmonic == "auto":
        if energy < threshold:
            return 1
        else:
            return 3
    # If we get here, the harmonic was not a valid option
    raise exceptions.InvalidHarmonic(
        f"Insertion device cannot accept harmonic: {harmonic}"
    )


def set_energy(
    energy: float,
    harmonic: Harmonic = None,
    positioners: DetectorList = ["energy"],
    harmonic_positioners: DetectorList = ["undulator_harmonic_value"],
):
    """Set the energy of the beamline, in electron volts.

    Moves both the mono energy, and the undulator energy with a
    calibrated offset.

    The *harmonic* parameter selects a harmonic for the undulator. If
    ``"auto"``, then the harmonic will be selected based on the
    energy. If *harmonic* is ``None``, then the current harmonic is
    used. If *harmonic* is an integer (e.g. 1, 3, 5) then this value
    will be used.

    Parameters
    ==========
    energy
      The target energy of the beamline, in electron-volts.
    harmonic

      Which harmonic to use for the undulator. Can be an integer
      (e.g. 1, 3, 5), ``None``, or ``"auto"``.

    """
    # Prepare arguments for undulator harmonic
    harmonic = auto_harmonic(energy, harmonic)
    if harmonic is not None:
        harmonic_positioners = beamline.devices.findall(name=harmonic_positioners)
        hargs = []
        for positioner in harmonic_positioners:
            hargs.extend([positioner, harmonic])
        yield from bps.mv(*hargs)
    # Prepare arguments for energy
    positioners = beamline.devices.findall(name=positioners)
    args = []
    for positioner in positioners:
        args.extend([positioner, energy])
    # Execute the plan
    yield from bps.mv(*args)


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
