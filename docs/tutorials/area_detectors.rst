=========================
Tutorial: Area Detectors
=========================

This tutorial covers the basics of using an area
detector. Specifically:

- :ref:`ad-loading`
- :ref:`ad-staging`
- :ref:`ad-xafs-scan`

.. _ad-loading:

Loading the Ophyd Device
========================

.. note::
   
   This tutorial assumes the area detector has already been configured
   in Haven for use at the beamline. For setup instructions, see
   :doc:`/topic_guides/area_detectors`.

First, open a terminal and run ``start_haven``. After a brief wait,
this will import some basic Haven and Bluesky objects and then present
you with an ipython terminal.

Next we will **retrieve the device from Haven's device registry**. In
this tutorial we will be using an Eiger S 500K area detector. We need
to know the device name. To find it, we will ask the haven registry
for all available devices.

.. code-block:: ipython

   In [1]: haven.registry.device_names
   Out[1]: 
   ['sim_motor',
    'eigerector',
    'energy',
    'monochromator',
    's25id-gige-A',
    'Shutter A',
    'Aerotech',
    'NHQ01_ch1',
    'NHQ01_ch2',
    'KB_slits',
    'eiger',
    'vortex_me4']

The second to last entry is the name of the device we want, so we will
now retrieve it from the device registry:

.. code-block:: ipython

   In [2]: eiger = haven.registry.find("eiger")


.. _ad-staging:
   
Verifying the Device Can Be Staged
==================================

If this is the first time the detector has been used since the IOC was
started, there may be additional steps required. To test this, we will
see if the device can be staged.

.. code-block:: ipython

   In [3]: eiger.stage()

If the above function **returns without error**, then the device can be
unstaged and is ready for use. Before we do that, lets just make sure we can trigger it.

.. code-block:: ipython
		
   In [4]: eiger.trigger().wait()
   
   In [5]: eiger.unstage()
		
However, if **staging causes and exception about an unprimed plugin**,
then we need to prime the plugin first. The following steps should prime the plugin:

- open the caQtDM panels (e.g. ``start_25idSimDet_caqtdm``)
- open the plugins panel (under *Plugins* click the *All* button
- Ensure the offending plugins are enabled
- In the original camera panel, click *Start* button next to "Acquire"
  to collect a frame

Now we can stage and trigger the detector.

.. code-block:: ipython

   In [4]: eiger.stage()

   In [5]: eiger.trigger().wait()
   
   In [6]: eiger.unstage()


.. _ad-xafs-scan:

Running an XAFS Scan
====================

First, we will verify that the detector is going to measure the correct signals for this detector:

.. code-block:: ipython

   In [7]: list(eiger.read_attrs)

Next, we will prepare the plan. By default, the
:py:func:`~haven.plans.xafs_scan.xafs_scan` plan will only measure the
ion chambers. To also trigger the area detector, we must include it as
a detector.

.. code-block:: ipython

   In [8]: detectors = [eiger, *ion_chambers]

Now we will **create an XAFS scan plan** with the following energies relative to the N-K edge (8333 eV):

- -200 eV to -30 eV

  - 10 eV steps
  - 1 second exposure
    
- -30 eV to +30 eV

  - 1 eV steps
  - 1 second exposure
    
- +30 eV to k=14 Å⁻

  - 0.05 Å⁻ steps
  - 1 second base exposure
  - k_weight = 0.5

.. code-block:: ipython

   In [9]: plan = haven.xafs_scan(-200, 10, 1, -30, 1, 1, 30, k_step=0.05, k_max=14, k_exposure=1, k_weight=0.5, E0="Ni_K", detectors=detectors)

Next we will summarize the plan to ensure that it is performing the steps we expect:

.. code-block:: ipython

   In [10]: summarize_plan(plan)

Inspect the output to ensure that it is measuring the correct detectors (``Read ['eiger', 'Iref', 'Ipreslit', 'It', 'IpreKB', 'I0dn', 'energy']``) and setting the correct energies (``energy -> 9069.77015484562``) and exposure times (``Iref_exposure_time -> 2.2221354183382798`` and ``eiger_cam_acquire_time -> 2.2221354183382798``).

Summarizing the plans consumes it, so we will build the plan again,
and **run it in the run engine** along with some meta-data describing
the sample and the reason we're measuring it:

.. code-block:: ipython

   In[12]: plan = haven.xafs_scan(-200, 10, 1, -30, 1, 1, 30, k_step=0.05, k_max=14, k_exposure=1, k_weight=0.5, E0="Ni_K", detectors=detectors)

   In[13]: RE(plan, sample_name="Ni test sample", purpose="training")
