==================================
Welcome to Vessim's Documentation!
==================================

Vessim is a versatile **co-simulation testbed for carbon-aware applications and
systems**.  It lets users connect domain-specific simulators for energy system
components such as renewable power generation, energy storage, and power flow
analysis with real software and hardware.  It is based on `mosaik
<https://mosaik.offis.de/>`_,  a general-purpose co-simulation framework.
Mosaik connects simulators of any language and real systems via TCP and ensures
their synchronization. It also offers an API for defining simulation scenarios. 

.. image:: source/_static/CarbonAware_vessim_Aspects.png
    :width: 480px
    :align: center

The documentation provides a guide explaining the concept of this project, two
examples to get you started with it and an API reference.


.. note::
    
    Vessim is in alpha stage and under active development. Functionality and
    documentation will improve in the next weeks and months.

.. toctree::
   :maxdepth: 3
   :hidden:
   :caption: Content:
 
   source/overview/index
   source/tutorials/index
   source/api_reference/index
   source/about_vessim/index