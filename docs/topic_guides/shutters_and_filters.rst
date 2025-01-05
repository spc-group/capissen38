####################
Shutters and Filters
####################

A shutter is any device that has "shutters" in its `_ophyd_labels_`
attribute.

.. contents:: Table of Contents
    :depth: 3

Automatic Shutter Control
=========================

To reduce radiation does, it is useful to include plans that
automatically open and close the shutters as needed. Additionally, the
run engine should be temporarily paused (suspeneded) when shutter
permit is lost.

Auto-Open Shutters
------------------

In the case of **radiation-sensitive samples**, the experiment may
require **keeping the shutter closed** except when collecting
data. Haven includes two preprocessors that can be used to
automatically open shutters that are closed:
:py:func:`~haven.preprocessors.open_shutters_decorator` and
:py:func:`~haven.preprocessors.open_shutters_wrapper`. Both the
end-station PSS shutter, and a secondary fast shutter can both be left
closed and then opened automatically only when needed for recording
data. This feature is enabled by default on plans in
:py:mod:`haven.plans` that trigger detectors (except for
:py:func:`haven.plans.record_dark_current`). :py:mod:`~haven.plans`
also includes wrapped versions of common Bluesky plans, like
:py:func:`haven.plans.scan`.

**Fast shutters** (those with ``"fast_shutters"`` in their
`_ophyd_labels_` attribute) will be opened before each "trigger"
message emitted by a plan, and closed after the subsequent "wait"
message. The "wait" message's *group* will be tracked, ensuring that
the fast shutters will only close after all triggers have been
awaited.

**Slow shutters** (those without ``"fast_shutters"`` in their
`_ophyd_labels_` attribute) will be opened at the start of the wrapped
plan, and closed again at the end.

Shutters that are open at the start of the plan, or haven *allow_open*
or *allow_close* set to ``False`` will be ignored.


Record Ion Chamber Dark Current
-------------------------------

The :py:func:`~haven.plans.record_dark_current` plan accepts a
sequence of shutter devices as an optional argument: *shutters*. Any
devices included will automatically be closed before measuring the
dark current, and opened again if they were initially open.


Suspend When Shutter Permit is Lost
-----------------------------------

.. note::

   This is still a work in progress. If you have an interest in this
   feature, please join the discussion.


Personnel Safety System (PSS) Shutters
======================================

The PSS shutters are typically large and slow to move. The APS PSS
shutters are controlled via three PVs:

- Open signal
- Close signal
- Beam blocking signal

Activating the open signal directly will instruct the IOC to open the
shutter, but will return a put complete before the shutter has
actually opened. This is not useful when actuating shutters in a
Bluesky plan. As such, the PSS shutters
(:py:class:`haven.devices.shutter.PssShutter`) are **implemented as
positioners** so that :py:meth:`haven.devices.shutter.PssShutter.set`
**completes only when** the beam blocking signal reports that the shutter
is open.

.. code-block:: python

    from haven.devices import PssShutter, ShutterState
    shutter = PssShutter(prefix="S255ID-PSS:FES:", name="front_end_shutter")]
    # Waits for the shutter to actually close:
    await shutter.set(ShutterState.CLOSED)

Or add the following to a **TOML file** read by the beamline startup:

.. code:: toml

    [[ pss_shutter ]]
    name = "front_end_shutter"
    prefix = "S255ID-PSS:FES:"
    # allow_close = true  # Default
    # allow_open = true  # Default

The optional arguments *allow_open* and *allow_close* control whether
the device should be allowed to open and close the shutter. Typically,
if either *allow_open* or *allow_close* are false, the shutter will be
ignored by tools that automatically actuate the shutters, like
:py:func:`~haven.preprocessors.open_shutters_wrapper` and
:py:func:`~haven.plans.record_dark_current`.
    

XIA PFCU-4 Filter Bank
=====================

One XIA PFCU controller can control four filters in a single
4-position PF4 filter box. Two filters in one box can be combined to
produce a shutter.

To **create a filter bank**:

.. code-block:: python

    from haven.devices import PFCUFilterBank
    filter_bank = PFCUFilterBank("255idc:pfcu0:", name="filter_bank")

Or add the following to a **TOML file** read by the beamline startup:

.. code-block:: toml
		
    [[ pfcu4 ]]
    name = "filter_bank1"
    prefix = "255idc:pfcu1:"
    
Each :py:class:`~haven.devices.xia_pfcu.PFCUFilterBank` device is a
positioner, and can be set with a string of the bits for all
filters. For example, ``await filter_bank.set("1100")`` will close
(``"1"``) filters 0 and 1, and open (``"0"``) filters 2 and 3. The
ophyd-async device uses this to set both blades on a shutter at once.


XIA PFCU Filter
---------------

The :py:class:`~haven.devices.xia_pfcu.PFCUFilterBank` has an
attribute *filters* which holds
:py:class:`~haven.devices.xia_pfcu.PFCUFilter` instances for the
individual filters in the bank. The **key for each filter** is its
position in the filter box, starting from 0. Some **filters may be
absent** if they are used for shutters, described below.


.. warning::

   A **TimeoutError** may occur when attempting to set multiple
   filters on the same filter bank concurrently. The IOC will often
   not process these requests properly, and one of the filters will
   not move. It is recommended to move filters individually, e.g.:

   .. code-block:: python

	RE(bps.mv(filter_bank.filters[0], FilterState.IN))
	RE(bps.mv(filter_bank.filters[1], FilterState.IN))

   instead of combining into a single move plan.


XIA PFCU Shutter
----------------

Two filters in one filter bank can be combined to produce a
shutter. Provide the indices (starting from 0) of the filters to use
when creating the filter bank:

.. code-block::

   filter_bank = PFCUFilterBank(..., shutters=[[3, 2]])

The first number listed (``3``) is the index of the filter holding the
top of the shutter, that is the filter that should be ``"In"`` to block
X-rays. The second number (``2``) is the index of the bottom
filter. **If the shutter is open when it should be closed**, consider
swapping the order of these numbers.

The resulting :py:class:`~haven.devices.xia_pfcu.PFCUShutter` instance
is available in the *shutters* device vector, with keys based on their
order in the original *shutters* argument. The recommended way to
**actuate the shutter** is by setting it directly rather than moving
the individual filters:

.. code-block:: python

    from haven.devices import ShutterState
    
    shutter = filter_bank.shutters[0]
    await shutter.set(ShutterState.CLOSED)

