from collections import namedtuple
from typing import Mapping

import matplotlib.pyplot as plt
import numpy as np
from bluesky import plans as bp
from lmfit.models import GaussianModel, StepModel

from ..instrument import beamline


def knife_scan(
    knife_motor,
    start: float,
    end: float,
    num: int,
    I0="I0",
    It="It",
    relative: bool = False,
    md: Mapping = {},
):
    """Plan to scan over a knife placed in the beam to measure its height.

    Parameters
    ==========
    knife_motor
      An ophyd device or name of a registered device that has a well
      defined edge attached to it.
    start
      Motor position at which to start scanning.
    end
      Motor position at which to finish scanning.
    num
      How many points to measure between *start* and *end*.
    I0
      Device or name of a registered ion chamber upstream from the
      knife.
    It
      Device or name of a registered ion chamber downstream from the
      knife.
    relative
      If true, *start* and *end* will be interpreted as relative to
      the current motor position.
    md
      Extra metadata to pass into the run engine.

    """
    md_ = dict(plan_name="knife_scan", **md)
    I0 = beamline.devices[I0]
    It = beamline.devices[It]
    knife_motor = beamline.devices[knife_motor]
    # Check for relative or absolute scan
    if relative:
        plan_func = bp.rel_scan
    else:
        plan_func = bp.scan
    # Compute the plan
    yield from plan_func([I0, It], knife_motor, start, end, num=num, md=md_)


def fit_step(x, y, plot=False, plot_derivative=False):
    """Extract beam properties from a step scan over the beam profile.

    Parameters
    ==========
    x
      Array of motor positions.
    y
      Array of measured values at each motor position
      (e.g. transmitted intensity).
    plot
      If true, plot the fitting results.
    plot_derivative
      If true, also fit and plot the derivative of the step scan.

    Returns
    =======
    properties
      A named tuple with the *size* and *position* of the beam, in
      units of *x*.

    """
    x = np.asarray(x)
    y = np.asarray(y)
    # Normalize data to start at zero
    y -= y[0]
    # Set up initial fitting parameters
    model = StepModel(form="erf")
    params = model.guess(y, x)
    half_max = (np.min(y) + np.max(y)) / 2
    center_idx = np.argmin(np.abs(y - half_max))
    center_guess = x[center_idx]
    params["center"].set(center_guess)
    # Invert the amplitude if we started with full transmission
    is_inverted = np.mean(y) < 0
    if is_inverted:
        params["amplitude"].set(-params["amplitude"].value)
    # Fit the model to the data
    result = model.fit(y, params=params, x=x)
    beam_position = result.values["center"]
    beam_hwhm = result.values["sigma"]
    # Do a fit of the derivative just for testing
    # Plot results
    if plot:
        # Plot knife scan and fit
        fig = plt.figure()
        result.plot(
            fig=fig,
            show_init=False,
            datafmt="x",
            xlabel="Knife position /µm",
            ylabel="Relative transmission",
        )
        ax_res, ax = fig.axes
        line_kw = dict(color="C0", ls=":")
        ax.axvline(beam_position, label="Beam position", **line_kw)
        ax.axhline(half_max, **line_kw)
        ax.text(beam_position, half_max, s=f"{beam_position:.2f}", color="C0")
        ax.axvline(beam_position - beam_hwhm, label="FWHM (y)", **line_kw)
        ax.axvline(beam_position + beam_hwhm, **line_kw)
        ax.legend()
    if plot and plot_derivative:
        # Fit derivative
        model = GaussianModel()
        dy = np.gradient(y, x)
        params = model.guess(dy, x)
        dresult = model.fit(dy, params=params, x=x)
        # Plot derivative of knife scan
        color2 = "C3"
        ax2 = ax.twinx()
        ax2.plot(x, dy, color=color2, label="Derivative", marker="x", ls="None")
        ax2.plot(x, dresult.eval(x=x), color=color2, alpha=0.5, label="Best fit")
        ax2.plot(
            x,
            np.gradient(result.eval(x=x), x),
            color=color2,
            alpha=0.5,
            ls="--",
            label="Step fit gradient",
        )
        dy_half_max = (np.min(dy) + np.max(dy)) / 2
        line_kw["color"] = color2
        ax2.axhline(dy_half_max, **line_kw)
        ax2.axvline(dresult.values["center"], **line_kw)
        dfwhm = dresult.values["fwhm"]
        ax2.axvline(
            dresult.values["center"] - dfwhm / 2, label="FWHM (dy/dx)", **line_kw
        )
        ax2.axvline(dresult.values["center"] + dfwhm / 2, **line_kw)
        ax2.legend()
        ax2.set_ylabel("Derivative /µm⁻")
    # Prepare results object
    Properties = namedtuple("Properties", ["position", "fwhm"])
    properties = Properties(position=beam_position, fwhm=2 * beam_hwhm)
    return properties


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
