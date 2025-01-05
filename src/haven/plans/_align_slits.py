"""A bluesky plan to scan the X-ray beam slits and then move the slits
to that position.

"""

import logging
import warnings

import lmfit
import numpy as np
from bluesky import plan_stubs as bps
from bluesky import plans as bp
from bluesky.callbacks import LiveFit
from bluesky.preprocessors import subs_decorator

__all__ = ["align_slits"]


log = logging.getLogger(__name__)


def align_slit_scan(slit_motor, ion_chamber):
    yield from bp.rel_scan([ion_chamber], slit_motor, -1, 1, 50)


def align_slits(slit_motors=[], ion_chamber=None):
    """Scan a range of values for the slit motor, and position the
    motor in the center.

    """
    for motor in slit_motors:
        # Set up the live fit object to process the results
        def gaussian(x, A, sigma, x0):
            return A * np.exp(-((x - x0) ** 2) / (2 * sigma**2))

        model = lmfit.Model(gaussian)
        init_guess = {"A": 2, "sigma": lmfit.Parameter("sigma", 3, min=0), "x0": -0.2}
        fit = LiveFit(model, ion_chamber.name, {"x": motor.name}, init_guess)
        scan = subs_decorator(fit)(align_slit_scan)
        # Execute the scan to find the center
        yield from scan(ion_chamber=ion_chamber, slit_motor=motor)
        # Move the slit motor to the center of the Gaussian peak
        new_center = fit.result.values["x0"]
        yield from bps.mv(motor, new_center)
        fit_quality = fit.result.chisqr
        # Logging, severity determined by quality of fit
        log.info(f"Centered slit '{motor.name}': {new_center} (X²: {fit_quality:.2f})")
        if fit_quality > 1:
            msg = (
                f"Poor fit while centering motor '{motor.name}'. X²: {fit_quality:.2f}"
            )
            log.warning(msg)
            warnings.warn(msg, RuntimeWarning)


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
