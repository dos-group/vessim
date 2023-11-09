# Vessim

[![PyPI version](https://img.shields.io/pypi/v/vessim.svg?color=52c72b)](https://pypi.org/project/vessim/)
![Tests](https://github.com/dos-group/vessim/actions/workflows/linting-and-testing.yml/badge.svg)
[![License](https://img.shields.io/pypi/l/vessim.svg)](https://pypi.org/project/vessim/)
[![Supported versions](https://img.shields.io/pypi/pyversions/vessim.svg)](https://pypi.org/project/vessim/)

Vessim is a versatile **co-simulation testbed for carbon-aware applications and systems**.
It lets users connect domain-specific simulators for energy system components like renewable power generation, 
energy storage, and power flow analysis with real software and hardware.

Vessim is in alpha stage and under active development.
Functionality and documentation will improve in the next weeks and months.


## Installation

If you are using Vessim for the first time, we recommend to clone and install this repository, so you have all
code and examples at hand:

```
pip install -e .
```

Alternatively, you can also install our [latest release](https://pypi.org/project/vessim/) 
via [pip](https://pip.pypa.io/en/stable/quickstart/):

```
pip install vessim
```


## Getting started

To execute our exemplary co-simulation scenario, run:

```
python examples/cosim_example.py
```

Software-in-the-Loop (SiL) simulation allows real computing systems to interact with Vessim at runtime.
We're currently working on better documentation on how to set up a full SiL scenario, but you can experiment with the existing
functionality by installing the "sil" extension (`pip install vessim[sil]`) and running:

```
python examples/sil_example.py
```


## Work in progress

Our team at the [Distributed and Operating Systems](https://distributedsystems.berlin/) group at TU Berlin is actively working to improve Vessim.
We are currently working on the following aspects and features:

- **Better documentation**: You can find the current WiP documentation [here](https://vessim.readthedocs.io/en/latest/)
- **Improving the scenario API**: We currently heavily rely on [Mosaik](https://mosaik.offis.de/)'s scenario interface for defining experiment, but want to offer a more opinionated, high-level API to improve usability.
- **Software-in-the-loop (SiL) capabilities**: The current SiL implementation is focussed around our exemplary use case presented in our [journal paper](https://doi.org/10.1002/spe.3275). We want this to become more general purpose, so users can implement custom interfaces for the communication of computing and energy systems.
- **Prodiving access to relevant datasets**: We're currently collectig relevant datasets for carbon-aware test cases such as solar production or carbon intensity traces to simplify the setup of test cases.
- **Integrating the SAM**: NREL's [System Advisor Model (SAM)](https://sam.nrel.gov/) will soon be available as a subsystem in Vessim.


## Publications

If you use Vessim in your research, please cite our vision paper:

- Philipp Wiesner, Ilja Behnke and Odej Kao. "[A Testbed for Carbon-Aware Applications and Systems](https://arxiv.org/pdf/2306.09774.pdf)" arXiv:2302.08681 [cs.DC]. 2023.
```
@misc{wiesner2023vessim,
    title={A Testbed for Carbon-Aware Applications and Systems}, 
    author={Wiesner, Philipp and Behnke, Ilja and Kao, Odej},
    year={2023},
    eprint={2306.09774},
    archivePrefix={arXiv},
    primaryClass={cs.DC}
}
```

Or our journal paper on software-in-the-loop similation for carbon-aware applications:
- Philipp Wiesner, Marvin Steinke, Henrik Nickel, Yazan Kitana, and Odej Kao. "[Software-in-the-Loop Simulation for Developing and Testing Carbon-Aware Applications](https://doi.org/10.1002/spe.3275)" Software: Practice and Experience, 53 (12). 2023.
```
@article{wiesner2023sil,
    author = {Wiesner, Philipp and Steinke, Marvin and Nickel, Henrik and Kitana, Yazan and Kao, Odej},
    title = {Software-in-the-loop simulation for developing and testing carbon-aware applications},
    journal = {Software: Practice and Experience},
    year = {2023},
    volume = {53},
    number = {12},
    pages = {2362-2376},
    doi = {https://doi.org/10.1002/spe.3275}
}
```
