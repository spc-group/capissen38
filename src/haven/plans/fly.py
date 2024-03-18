from collections import OrderedDict, abc
from typing import Mapping, Sequence, Union
from itertools import chain

import numpy as np
from bluesky import plan_patterns
from bluesky import plan_stubs as bps
from bluesky import plans as bp
from bluesky import preprocessors as bpp
from ophyd import Device
from ophyd.flyers import FlyerInterface
from ophyd.status import StatusBase

__all__ = ["fly_scan", "grid_fly_scan"]


def fly_line_scan(detectors: list, flyer, start, stop, num, extra_signals=()):
    """A plan stub for fly-scanning a single trajectory."""
    # Calculate parameters for the fly-scan
    step_size = abs(start - stop) / (num - 1)
    yield from bps.mv(flyer.start_position, start)
    yield from bps.mv(flyer.end_position, stop)
    yield from bps.mv(flyer.step_size, step_size)
    # Perform the fly scan
    flyers = [flyer, *detectors]
    for flyer_ in flyers:
        yield from bps.kickoff(flyer_, wait=True)
    for flyer_ in flyers:
        yield from bps.complete(flyer_, wait=True)
    # Collect the data after flying
    collector = FlyerCollector(
        primary_flyers=detectors, secondary_flyers=[flyer], name="flyer_collector", extra_signals=extra_signals
    )
    yield from bps.collect(collector)
    yield from bps.collect(flyer)


# @baseline_decorator()
def fly_scan(
    detectors: Sequence[FlyerInterface],
    flyer: FlyerInterface,
    start: float,
    stop: float,
    num: int,
    md: Mapping = {},
):
    """Do a fly scan with a 'flyer' motor and some 'flyer' detectors.

    Parameters
    ----------
    detectors
      List of 'readable' objects that support the flyer interface
    flyer
      The thing going to get moved.
    start
      The center of the first pixel in *flyer*.
    stop
      The center of the last measurement in *flyer*.
    num
      Number of measurements to take.
    md
      metadata

    Yields
    ------
    msg
      'kickoff', 'wait', 'complete, 'wait', 'collect' messages

    """
    # Stage the devices
    devices = [flyer, *detectors]
    # Prepare metadata
    md_ = {
        "plan_name": "fly_scan",
        "motors": [flyer.name],
        "detectors": [det.name for det in detectors],
        "plan_args": {
            "detectors": list(map(repr, detectors)),
            "flyer": repr(flyer),
            "start": start,
            "stop": stop,
            "num": num,
        },
    }
    md_.update(md)
    # Execute the plan
    line_scan = fly_line_scan(detectors, flyer, start, stop, num)
    line_scan = bpp.run_wrapper(line_scan, md=md_)
    line_scan = bpp.stage_wrapper(line_scan, devices)
    yield from line_scan


# @baseline_decorator()
def grid_fly_scan(
    detectors: Sequence[FlyerInterface],
    *args,
    snake_axes: Union[bool, Sequence[Device]] = False,
    md: Mapping = {},
):
    """Scan over a mesh with one of the axes collecting without stopping.

    Parameters
    ----------
    detectors
      list of 'readable' objects
    *args
      patterned like::

        motor1, start1, stop1, num1,
        motor2, start2, stop2, num2,
        ...
        flyer, flyer_start, flyer_stop, flyer_num

      The first motor is the "slowest", the outer loop. The last
      motor should be flyable.
    snake_axes
      which axes should be snaked, either ``False`` (do not snake any axes),
      ``True`` (snake all axes) or a list of axes to snake. "Snaking" an axis
      is defined as following snake-like, winding trajectory instead of a
      simple left-to-right trajectory. The elements of the list are motors
      that are listed in `args`. The list must not contain the slowest
      (first) motor, since it can't be snaked.
    md: dict, optional
      metadata

    Yields
    ------
    msg
      'stage', 'open_run', 'mv', 'kickoff', 'wait', 'complete, 'wait',
      'collect', 'close_run', 'stage' messages.

    """
    # Extract the step-scan vs fly-scan arguments
    *step_args, flyer, fly_start, fly_stop, fly_num = args
    # Handle giving snaked axes as a list
    step_chunks = list(plan_patterns.chunk_outer_product_args(step_args))
    num_steppers = len(step_chunks)
    motors = [m[0] for m in step_chunks]
    all_motors = [*motors, flyer]
    if isinstance(snake_axes, abc.Iterable) and not isinstance(snake_axes, str):
        snake_steppers = snake_axes.copy()
        try:
            snake_steppers.remove(flyer)
        except ValueError:
            snake_flyer = False
        else:
            snake_flyer = True
        # Save for metadata processing
        snaking = [
            (motor in snake_steppers) for motor, start, stop, num, snake in step_chunks
        ]
        snaking = (False, *snaking[1:], snake_flyer)
    else:
        snake_steppers = snake_axes
        snake_flyer = snake_axes
        snaking = [False, *[snake_axes for _ in step_chunks[1:]], snake_flyer]
    # Prepare metadata
    chunk_args = list(plan_patterns.chunk_outer_product_args(args))
    md_args = []
    motor_names = []
    for i, (motor, start, stop, num, snake) in enumerate(chunk_args):
        md_args.extend([repr(motor), start, stop, num])
        motor_names.append(motor.name)
    num_points = np.prod([num for motor, start, stop, num, snake in chunk_args])
    md_ = {
        "shape": tuple(num for motor, start, stop, num, snake in chunk_args),
        "extents": tuple(
            [start, stop] for motor, start, stop, num, snake in chunk_args
        ),
        "plan_args": {
            "detectors": list(map(repr, detectors)),
            "args": md_args,
        },
        "plan_name": "grid_fly_scan",
        "num_points": num_points,
        "num_intervals": num_points - 1,
        "motors": tuple(motor_names),
        "snaking": snaking,
        "hints": {},
    }
    # Add metadata hints for plotting, etc
    md_["hints"].setdefault("gridding", "rectilinear")
    try:
        md_["hints"].setdefault(
            "dimensions", [(m.hints["fields"], "primary") for m in all_motors]
        )
    except (AttributeError, KeyError):
        ...
    md_.update(md)
    # Set up the plan
    per_step = Snaker(
        snake_axes=snake_flyer,
        flyer=flyer,
        start=fly_start,
        stop=fly_stop,
        num=fly_num,
        extra_signals=motors,
    )
    uid = yield from bp.grid_scan(
        detectors,
        *step_args,
        snake_axes=snake_steppers,
        per_step=per_step,
        md=md_,
    )
    return uid


class Snaker:
    """Executes 1-D fly line scans in a snaking motion.

    Each call of the snaker executes the same fly-scan, but supports
    alternating scan directions to save time.

    This callable's signature is compatible with bluesky's
    ``per_step`` option for scans, so instead of just reading a
    detector, a whole fly-scan is performed."

    """

    reverse: bool = False

    def __init__(self, snake_axes, flyer, start, stop, num, extra_signals):
        self.snake_axes = snake_axes
        self.flyer = flyer
        self.start = start
        self.stop = stop
        self.num = num
        self.extra_signals = extra_signals

    def __call__(self, detectors, step, pos_cache):
        # Move the step-scanning motors to the correct position
        yield from bps.move_per_step(step, pos_cache)
        # Determine line scans range based on snaking
        start, stop = (self.start, self.stop)
        if self.reverse and self.snake_axes:
            start, stop = stop, start
        self.reverse = not self.reverse
        # Launch the fly scan
        yield from fly_line_scan(
            detectors,
            flyer=self.flyer,
            start=start,
            stop=stop,
            num=self.num,
            extra_signals=step.keys(),
        )


class FlyerCollector(FlyerInterface, Device):
    """A faux device for collecting data from other flyers.

    Useful for combining individual flyer streams into a single unified stream.

    Imagine a fly scan where a motor moves contuously over a region
    while triggering one or more detectors. Each flyer will generate a
    data stream independent of the others, but it may be desirable to
    have a single "primary" data stream with the output of each
    detector along with the corresponding motor position.

    This flyer creates a data stream named as the value of
    *stream_name*, where the values in *primary_flyers*
    (e.g. detectors) are included together, and the values for
    *secondary_flyers* (e.g. motor) are predicted based on timestamps
    read from *primary_flyers*.

    Expects each device in *secondary_flyers* to have a method
    ``predict(self, timestamp: float)`` that accepts the timestamp for
    the measurement and returns a datum dictionary, similar to those
    yielded by :py:meth:`ophyd.FlyerInterface.collect`.

    Parameters
    ==========
    primary_flyers
      The flyer devices that determine the structure of the new data
      stream.
    secondary_flyers
      The flyer devices that will be interpolated to match those in
      *primary_flyers* in the new data stream.
    stream_name
      What to call the newly created data stream.
    extra_signals
      Signals whose *read* method will be added to the new data stream.
    
    """

    
    stream_name: str
    flyers: list

    def __init__(
        self, primary_flyers: Sequence, secondary_flyers: Sequence = [], stream_name: str = "primary", extra_signals: Sequence = (), *args, **kwargs
    ):
        self.primary_flyers = primary_flyers
        self.secondary_flyers = secondary_flyers
        self.stream_name = stream_name
        self.extra_signals = extra_signals
        super().__init__(*args, **kwargs)

    def kickoff(self):
        return StatusBase(success=True)

    def complete(self):
        return StatusBase(success=True)

    def collect(self):
        collections = [iter(flyer.collect()) for flyer in self.primary_flyers]
        while True:
            event = {
                "data": {},
                "timestamps": {},
            }
            try:
                for coll in collections:
                    datum = next(coll)
                    event["data"].update(datum["data"])
                    event["timestamps"].update(datum["timestamps"])
            except StopIteration:
                break
            # Use the median time stamps for the overall event time
            timestamps = []
            for ts in event["timestamps"].values():
                timestamps.extend(np.asarray(ts).flatten())
            # Predict the position of the secondary flyers based on timestamp
            curr_timestamp = np.median(timestamps)
            for flyer in self.secondary_flyers:
                datum = flyer.predict(curr_timestamp)
                event["data"].update(datum["data"])
                event["timestamps"].update(datum["timestamps"])
                ts = list(datum["timestamps"].values())
                timestamps.extend(np.asarray(ts).flatten())
            # Determine the event time based on average timestamp
            event["time"] = np.median(timestamps)
            # Add extra non-flying signals (not inc. in event time)
            for signal in self.extra_signals:
                for signal_name, reading in signal.read().items():
                    event["data"][signal_name] = reading["value"]
                    event["timestamps"][signal_name] = reading["timestamp"]
            yield event

    def describe_collect(self):
        desc = OrderedDict()
        for flyer in chain(self.primary_flyers, self.secondary_flyers):
            for stream, this_desc in flyer.describe_collect().items():
                desc.update(this_desc)
        # Add extra signals, e.g. slow motor during a grid fly scan
        for signal in self.extra_signals:
            desc.update(signal.describe())
        return {self.stream_name: desc}


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
