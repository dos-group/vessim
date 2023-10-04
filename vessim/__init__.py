"""
## What is vessim?

Vessim is a versatile **co-simulation testbed for carbon-aware applications and systems**. 
It lets users connect domain-specific simulators for energy system components such as renewable power generation, energy storage, and power flow analysis with real software and hardware.
It is based on [mosaik](https://mosaik.offis.de/), a general-purpose co-simulation framework.
Mosaik connects simulators of any language and real systems via TCP and ensures their synchronization. It also offers an API for defining simulation scenarios. 

Vessim is in alpha stage and under active development. Functionality and documentation will improve in the next weeks and months.

## What can I do with it?

Vessim allows users to test real applications within a co-simulation testbed composed of domain-specific simulators on energy system components.
The following Figure shows the different aspects of carbon-aware systems that can be investigated through Vessim.
<div style="text-align: center;">
    <img src="../docs/pics/CarbonAware_vessim_Aspects.png" alt="Carbon Aware Vessim Aspects" width="700">
</div>
As depicted in the above Figure, Vessim enables research on various aspects related to the interplay of energy and computing systems.

- **Energy system composition**: Examine how integrating components like solar panels affects computing systems. Evaluate requirements for energy-autonomous data centers and potential impacts of future technologies.
- **Energy system abstractions**: Vessim simplifies microgrid complexities through simulation, focusing on safety and carbon-aware applications while virtualizing energy systems.
- **Energy system interfaces**: Investigate integration of new components, handling external data, and ensuring secure, controlled access across geo-distributed systems.
- **Carbon-aware applications**: Vessim allows rapid prototyping of carbon-aware computing ideas, offering access to current standards and promoting common dataset use.

Besides facilitating research, Vessim can support the development and quality assurance of carbon-aware applications and systems. 
For example, it can be applied in continuous integration testing, or used to validate software roll-outs in a controlled environment.
Additionally, using Vessim as a digital twin, carbon-aware datacenters can predict future system states, aid decision-making, and assess risks during extreme events like power outages.

## How does it work?
<div style="text-align: center;">
    <img src="../docs/pics/Experiment_SiL_Design.png" alt="Experiment SiL Design" width="700">
</div>

## ⚙️ Installation

If you are using Vessim for the first time, we recommend to clone and install this repository, so you have all code and examples at hand:

```
$ pip install -e .
```


Alternatively, you can also install our [latest release](https://pypi.org/project/vessim/)
via [pip](https://pip.pypa.io/en/stable/quickstart/):

```
$ pip install vessim
```


## 🚀 Getting started

To ease your start with Vessim, we provide two examples:

### cosim_example

The [cosim_example](https://github.com/dos-group/vessim/blob/main/examples/cosim_example.py) runs a fully simulated example scenario over the course of two days.
See `cosim_example` for more details.

### sil_example

The [sil_example](https://github.com/dos-group/vessim/blob/main/examples/sil_example.py) is a co-simulation example with software-in-the-loop. 
This scenario builds on cosim_example.py but connects to a real computing system through software-in-the-loop integration. This example is experimental and documentation is still in progress.
See `sil_example` for more details.


## Publications

- Philipp Wiesner, Ilja Behnke, and Odej Kao. "[A Testbed for Carbon-Aware Applications and Systems](https://arxiv.org/pdf/2306.09774.pdf)". arXiv:2302.08681 [cs.DC]. 2023.

## Contact

Vessim was developed at the research group for [Distributed and Operating Systems (DOS)](https://www.dos.tu-berlin.de), at TU Berlin.

In case of questions, please reach out to [Philipp Wiesner](https://www.dos.tu-berlin.de/menue/people/wiesner_philipp/).
"""
