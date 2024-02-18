==================================
Welcome to Vessim's Documentation!
==================================

Vessim is a versatile **co-simulation testbed for carbon-aware applications and
systems**. It lets users connect domain-specific simulators for energy system
components such as renewable power generation and energy storage with *real*
software and hardware while abstracting microgrid complexities.

Vessim is based on |mosaik| , a general-purpose co-simulation framework.

.. |mosaik| image:: _static/mosaik.png
    :height: 3 em
    :target: https://mosaik.offis.de 

.. image:: _static/CarbonAware_vessim_Aspects.png
    :width: 75%
    :align: center

This documentation guides you through the concepts of Vessim, presents usage
tutorials to get you started, and provides the API reference.

.. note::
    
    Vessim is in alpha stage and under active development. Functionality and
    documentation will improve in the next weeks and months.

What can I do with it?
======================

    - **Carbon-aware applications**: Vessim allows rapid prototyping of carbon-aware computing ideas, offering access to current standards and promoting common dataset use.
    - **Energy system composition**: Examine how integrating components like solar panels affects computing systems and evaluate requirements for energy-autonomous data centers.
    - **Digital Twin**: Predict future system states in carbon-aware datacenters, aid decision-making, and assess risks during extreme events like power outages.
    - **Quality Assurance**: Apply Vessim in continuous integrating testing or use it to validate software roll-outs in a controlled environment.


Further Reading & Research
==========================

If you'd like to dive deeper into the base concepts of this project, you can
read more in our our vision paper, `"A Testbed for Carbon-Aware Applications and
Systems" <https://arxiv.org/pdf/2306.09774.pdf>`_ by Philipp Wiesner, Ilja
Behnke and Odej Kao.

.. image:: _static/vessim_paper.png
    :width: 40%
    :align: center


If you use Vessim in your research, please cite it like the following:

.. code-block:: text

    @misc{wiesner2023vessim,
        title={A Testbed for Carbon-Aware Applications and Systems}, 
        author={Wiesner, Philipp and Behnke, Ilja and Kao, Odej},
        year={2023},
        eprint={2306.09774},
        archivePrefix={arXiv},
        primaryClass={cs.DC}
    }


.. toctree::
   :maxdepth: 3
   :hidden:
   :caption: Content:
 
   main_components/index
   installation/index
   tutorials/index
   api_reference/index
   about_vessim/index