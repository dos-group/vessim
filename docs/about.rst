============
About Vessim
============

Most research on energy-aware and carbon-aware computing relies on simulations, as globally distributed hardware testbeds are rare and costly.
Vessim addresses this gap by simplifying and unifying simulation-based evaluations and enabling continuous testing of emerging applications.

Vessim is developed at the `Distributed and Operating Systems (DOS) <https://www.dos.tu-berlin.de>`_ group at TU Berlin and is led by `Philipp Wiesner <https://philippwiesner.org>`_.
Active development began in March 2023 with initial funding from the `German Federal Ministry of Education and Research (BMBF) <https://www.bmbf.de/>`_ as part of the Software Campus project `SYNERGY <https://softwarecampus.de/en/projekt/synergy-synergies-of-distributed-artificial-intelligence-and-renewable-energy-generation/>`_.

We thank everyone who has contributed to Vessim over the past years, especially Marvin Steinke, Paul Kilian, and Amanda Malkowski.


Publications
============

If you use Vessim in your research, please cite our paper:

    Philipp Wiesner, Ilja Behnke, Paul Kilian, Marvin Steinke, and Odej Kao. "`Vessim: A Testbed for Carbon-Aware Applications and Systems. <https://arxiv.org/pdf/2306.09774.pdf>`_" 3rd Workshop on Sustainable Computer Systems (HotCarbon). 2024.

.. raw:: html

   <details>
   <summary><a>Bibtex</a></summary>

.. code-block:: text

    @inproceedings{wiesner2024vessim,
        title     = {Vessim: A Testbed for Carbon-Aware Applications and Systems},
        author    = {Wiesner, Philipp and Behnke, Ilja and Kilian, Paul and Steinke, Marvin and Kao, Odej},
        booktitle = {3rd Workshop on Sustainable Computer Systems (HotCarbon)},
        year      = {2024},
    }

.. raw:: html

   </details><br>


For details in Vessim's software-in-the-loop simulation methodology, refer to our journal paper:

    Philipp Wiesner, Marvin Steinke, Henrik Nickel, Yazan Kitana, and Odej Kao. "`Software-in-the-Loop Simulation for Developing and Testing Carbon-Aware Applications <https://onlinelibrary.wiley.com/doi/10.1002/spe.3275>`_" Software: Practice and Experience, 53 (12). 2023.

.. raw:: html

   <details>
   <summary><a>Bibtex</a></summary>

.. code-block:: text

    @article{wiesner2023sil,
        author    = {Wiesner, Philipp and Steinke, Marvin and Nickel, Henrik and Kitana, Yazan and Kao, Odej},
        title     = {Software-in-the-loop simulation for developing and testing carbon-aware applications},
        journal   = {Software: Practice and Experience},
        year      = {2023},
        volume    = {53},
        number    = {12},
        pages     = {2362-2376},
        doi       = {https://doi.org/10.1002/spe.3275}
    }

.. raw:: html

   </details>


Publications using Vessim
=========================

- Julius Irion, Philipp Wiesner, Jonathan Bader, and Odej Kao. "`Optimizing Microgrid Composition for Sustainable Data Centers <https://dl.acm.org/doi/full/10.1145/3731599.3767562>`_". Sustainable Supercomputing Workshop at SC. 2025.
- Miray Özcan, Philipp Wiesner, Philipp Weiß, and Odej Kao. "`Quantifying the Energy Consumption and Carbon Emissions of LLM Inference via Simulations <https://arxiv.org/pdf/2507.11417>`_". Workshop on Performance and Energy Efficiency in Concurrent and Distributed Systems (PECS) at Euro-PAR. 2025.
- Paul Kilian, Philipp Wiesner, and Odej Kao. "`Choosing the Right Battery Model for Data Center Simulations <https://arxiv.org/pdf/2506.17739>`_". 1st International Workshop on Low Carbon Computing (LOCO). 2024.
- Philipp Wiesner, Ramin Khalili, Dennis Grinwald, Pratik Agrawal, Lauritz Thamsen, and Odej Kao. "`FedZero: Leveraging Renewable Excess Energy in Federated Learning <https://dl.acm.org/doi/10.1145/3632775.3639589>`_". 15th ACM International Conference on Future and Sustainable Energy Systems (e-Energy). 2024.


Roadmap
=======

We are currently working on the following aspects and features:

- **Vessim X Flower**: We are working on integrating Vessim into the federated learning framework `Flower <https://flower.ai>`_.
- **Vessim X Vidur**: We are working on integrating Vessim into the LLM simulator `Vidur <https://github.com/microsoft/vidur>`_.
- **System Advisor Model (SAM)**: We are working on integrating NREL's `SAM <https://sam.nrel.gov/>`_ as a subsystem in Vessim, allowing for better simulation of solar arrays, wind farms, and other types of renewable energy generators.
- **Battery degradation**: We are working on integrating NREL's `BLAST-Lite <https://github.com/NREL/BLAST-Lite>`_ for modeling battery lifetime and degradation
- **Calibration**: We are working on a methodology for calibrating Vessim simulations on real hardware testbeds.


License
=======

Vessim is released under the `MIT License
<https://github.com/dos-group/vessim/blob/main/LICENSE>`_. 
