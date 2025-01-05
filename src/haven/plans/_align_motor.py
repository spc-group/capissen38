import logging
import time
import warnings

from apstools.plans.alignment import lineup
from bluesky import plan_stubs as bps
from bluesky.callbacks import best_effort
from bluesky.preprocessors import subs_wrapper

from ..preprocessors import shutter_suspend_decorator

log = logging.getLogger(__name__)


__all__ = ["align_motor", "align_pitch2"]


# @shutter_suspend_decorator()
def align_pitch2(
    pitch2, distance=200, reverse=False, detector="I0", bec=None, feature="cen", md={}
):
    """Tune the monochromator 2nd crystal pitch motor.

    Find and set the position of maximum intensity in the ion chamber
    "I0". The scanning range is relative to the current motor
    position, and will go *distance* above and below it. For example,
    if the current position is 1000, ``distance=200`` will scan from
    800 to 1200.

    Parameters
    ==========
    pitch2
      The pitch2 motor to use
    bec
      A bluesky best effort callback for finding the peak position.
    distance
      Relative distance to scan in either direction.
    reverse
      Whether the scan goes low-to-high (False) or high-to-low (True).
    detector
      Which detector name to use.
    feature
      Which feature of the peak to use for alignment.
    md
      Extra metadata to pass into the run engine.

    """
    md_ = dict(plan_name="align_pitch2")
    md_.update(md)
    # Prepare and run the plan
    yield from align_motor(
        detector=detector,
        motor=pitch2,
        distance=distance,
        reverse=reverse,
        bec=bec,
        feature=feature,
        md=md_,
    )


@shutter_suspend_decorator()
def align_motor(
    detector, motor, distance=200, reverse=False, bec=None, feature="cen", md={}
):
    """Center the given motor using the beam intensity.

    Find and set the position of maximum intensity in the ion chamber
    *detector*. The scanning range is relative to the current motor
    position, and will go *distance* above and below it. For example,
    if the current position is 1000, ``distance=200`` will scan from
    800 to 1200.

    Parameters
    ==========
    detector
      The detector device to use for measuring signals.
    motor
      The motor to use for alignment.
    bec
      A bluesky best effort callback for finding the peak position.
    distance
      Relative distance to scan in either direction.
    reverse
      Whether the scan goes low-to-high (False) or high-to-low (True).
    feature
      Which feature of the peak to use for alignment.
    md
      Extra metadata to pass into the run engine.

    """
    msg = (
        "The ``align_motor`` plan is deprecated. "
        "Consider using ``bluesky.plans.tune_centroid`` instead"
    )
    warnings.warn(msg, DeprecationWarning)
    # Prepare metadata
    md_ = dict(plan_name="align_motor")
    md_.update(md)
    # Set up the best effort callback
    if bec is None:
        bec = best_effort.BestEffortCallback()
        bec.disable_table()
    # Determine plan parameters
    start, end = (distance, -distance) if reverse else (-distance, distance)
    # Resolve motors and detectors
    detectors = [detector]
    if hasattr(detector, "raw_counts"):
        detectors.insert(0, detector.raw_counts)
    plan = lineup(
        detectors, motor, start, end, npts=40, feature=feature, bec=bec, md=md_
    )
    plan = subs_wrapper(plan, bec)
    yield from plan
    # Wait for the callback to catch up
    t0 = time.time()
    timeout = 5
    det_name = detectors[0].name
    while time.time() - t0 < timeout:
        new_value = bec.peaks[feature].get(det_name)
        if new_value is not None:
            if feature in ["max", "min"]:
                # Max and min also include the y-value
                new_value, y_value = new_value
            break
    # Set the motor to the new value (from below accounting for hysteresis)
    if new_value is None:
        # Didn't find a peak position
        msg = (
            f"No peak position found for {det_name},"
            f"motor '{motor.name}' will not be set."
        )
        log.error(msg)
        warnings.warn(msg)
    else:
        yield from bps.mv(motor, new_value - abs(end - start) / 2)
        yield from bps.mv(motor, new_value)


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
