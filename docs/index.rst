=================
Welcome to Vessim
=================

What is vessim?
===============

Vessim is a versatile **co-simulation testbed for carbon-aware applications and systems**. 
It lets users connect domain-specific simulators for energy system components such as renewable power generation, energy storage, and power flow analysis with real software and hardware.
It is based on `mosaik <https://mosaik.offis.de/>`_,  a general-purpose co-simulation framework.
Mosaik connects simulators of any language and real systems via TCP and ensures their synchronization. It also offers an API for defining simulation scenarios. 

Vessim is in alpha stage and under active development. Functionality and documentation will improve in the next weeks and months.

What can I do with it?
======================

Vessim allows users to test real applications within a co-simulation testbed composed of domain-specific simulators on energy system components.
The following Figure shows the different aspects of carbon-aware systems that can be investigated through Vessim.

.. image:: _static/CarbonAware_vessim_Aspects.png
    :width: 450px
    :align: center

As depicted in the above Figure, Vessim enables research on various aspects related to the interplay of energy and computing systems.

    - **Energy system composition**: Examine how integrating components like solar panels affects computing systems. Evaluate requirements for energy-autonomous data centers and potential impacts of future technologies.
    - **Energy system abstractions**: Vessim simplifies microgrid complexities through simulation, focusing on safety and carbon-aware applications while virtualizing energy systems.
    - **Energy system interfaces**: Investigate integration of new components, handling external data, and ensuring secure, controlled access across geo-distributed systems.
    - **Carbon-aware applications**: Vessim allows rapid prototyping of carbon-aware computing ideas, offering access to current standards and promoting common dataset use.

Besides facilitating research, Vessim can support the development and quality assurance of carbon-aware applications and systems. 
For example, it can be applied in continuous integration testing, or used to validate software roll-outs in a controlled environment.
Additionally, using Vessim as a digital twin, carbon-aware datacenters can predict future system states, aid decision-making, and assess risks during extreme events like power outages.

How does it work?
=================

.. image:: _static/Experiment_SiL_Design.png
    :width: 450px
    :align: center

.. toctree::
   :maxdepth: 4
   :hidden:
   :caption: Content:
   
   references/overview
   references/examples
   docstrings/modules
   references/aboutvessim  
   

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`