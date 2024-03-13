======
Vessim
======

Vessim is a versatile **co-simulation testbed for carbon-aware applications and systems** which connects domain-specific simulators for renewable power generation and energy storage with real software and hardware.

.. image:: _static/vessim_overview.png
    :width: 100%
    :alt: Vessim Overview


What can I do with Vessim?
==========================

Vessim simulates energy systems that interact with real or simulated computing systems for:

    - **Carbon-aware applications**: Simulated microgrids offer real-time visibility and control via APIs, enabling the development of novel applications that interact with their energy system.
    - **Energy system composition**: Examine how the integration of solar panels, wind energy, or batteries would affect the energy mix of your datacenters.
    - **Digital Twins**: Predict future system states in carbon-aware datacenters, aid decision-making, and assess risks during extreme events like power outages.
    - **Quality Assurance**: Apply Vessim in continuous integrating testing or use it to validate software roll-outs in a controlled environment.

Vessim is based on `Mosaik <https://mosaik.offis.de>`_, a general-purpose co-simulation framework.
It can simulate large numbers of microgrids in parallel, comes with ready-to-use datasets, can execute simulated experiments faster than real-time, and is easily extendable with new simulators of any platform through Mosaik's TCP interface.


Installation
============

You can install our `latest release <https://pypi.org/project/vessim/>`_ via
`pip <https://pip.pypa.io/en/stable/getting-started/>`_:

.. code-block:: console

    pip install vessim

If you require software-in-the-loop (SiL) capabilities, you can install the
`sil`` extra:

.. code-block:: console

    pip install vessim[sil]

For complex scenarios that involve custom co-simulation actors we recommend
cloning and editing this depository directly.



.. toctree::
    :maxdepth: 3
    :hidden:
    :caption: Content:

    Overview <self>
    concepts
    tutorials/index
    api_reference/index
    about