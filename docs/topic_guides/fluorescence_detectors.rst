#######################
Fluorescence Detectors
#######################

.. contents:: Table of Contents
    :depth: 3

.. warning::

   Fluorescence detectors are in the process of being transitioned
   from the older, threaded Ophyd library to *ophyd-async*. The
   documentation below **should be accurate for Xspress3** devices,
   but **not for DXP** based devices as those have not been
   transitioned to ophyd-async yet.

Haven supports two varieties of fluorescence detector:

- Xspress3
- DXP (XIA's XMAP, Saturn, and Mercury)

The support for these two electronics is very different, but the basic
idea is the same. To acquire a frame, each detector will first
configure its file writer, then trigger the detector. This will result
in a file on disk with the measured spectra from all elements in the
detector. The data can then be retrieved with something like Tiled,
which can open the data file and serve the enclosed data. All these
steps happen out-of-sight of the user, provided the detector is used
with the updated Ophyd-async devices.


Specifying Detectors in Configuration
=====================================

To add new detectors to the beamline, new sections should be added to
the *iconfig.toml* file. Each section should be labeled ``[[ <class>
]]``, where ``<class>`` specifies which interface is present
(``"dxp"`` for XIA DXP/XMAP or ``"xspress3"`` for Xspress3).

The following parameters can then be included:

*name*
  The python-friendly name to use for this device.
*prefix*
  The PV prefix for the EPICS IOC, including the trailing colon.

.. code-block:: toml
   :caption: example_iconfig.toml		
		
   [[ dxp ]]
   prefix = "20xmap4b:"
   name = "vortex_me4"

   [[ xspress ]]
   prefix = "dp_xsp3_2:"
   name = "vortex_ex"

The device can then be retrieved by its name for use in Bluesky plans.

.. code-block:: python
   
   import haven

   # Get individual fluorescence detectors
   vortex_4elem = haven.beamline.devices["vortex_me4"]
   vortex_1elem = haven.beamline.devices["vortex_ex"]

   # Get all fluorescence detectors of any kind (e.g. DXP, Xspress3, etc.)
   detectors = haven.beamline.devices.findall(label="fluorescence_detectors")


Why can't I…
############

Previously, some steps were performed during data acquisition by the
IOC that have now been moved to other parts of the system. These
decisions were made largely to simplify data acquisition and ensure
this process happens smoothly.

…set regions of interest (ROIs)?
--------------------------------

ROIs should now be done during analysis prior to visualization using
tools like xray-larch.

ROIs are typically set so that each one roughly corresponds to the
intensity of a given emission line (e.g. Fe–K). Doing this during data
acquisition is convenient for later visualization, since no specialized
plotting tools are needed. However, there are a few drawbacks.

Setting ROIs during acquisition mixes measured data with processed
data, giving the impression that the Fe–K emission was actually
measured, when in reality a rough approximation was performed. This
further gives the impression that no further analysis is needed. In
reality, a full spectrum analysis such as that available in xray-larch
is required to properly derive estimates of the elemental emission
signals. This analysis will account for background subtraction and
multiple overlapping peaks, among other things.

Additionally, calculating ROIs adds additional time to each detector
frame acquisition. This may introduce a race condition. If plugins are
not set to block, then the PVs for the various plugins may not be
updated by the time the data acquisition system thinks the frame is
done. The only reliable means to ensure plugins have completed
processing is to set them to block, which adds additional time to each
acquisition. Given that ROI calculations are trivial for a full
dataset, this is best left to the analaysis and visualization phases
of the measurement.

…disable individual elements?
-----------------------------

Ophyd-async does not consider the elements of the detector
individually. The detector is responsible for collecting its own data
and saving it to disk. As a consequence, it is not possible to enable
or disable individual elements during acquisition. Since no data
reduction or analysis takes place during acquisition, this should not
have any impact on the results. Instead, the entire spectrum for each
element is saved to disk using the IOCs file writer plugins. **Whether
to include a given element** is then a decision that must be made
during analysis and visualization.

…view the summed spectrum?
--------------------------

Since the data coming from the fluorescence detector are effectively
an area detector image, it is simple to calculate the summed spectrum
from all the spectra of the individual elements. While the EPICS IOCs
typically include a PV for this summed spectrum, it is not trivial to
include this summed spectrum in the resulting HDF5 file. Instead,
plotting tools, like Haven's run browser, should include a feature for
dimensionality reduction.
