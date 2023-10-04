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


## ⚙️ Installation

If you are using Vessim for the first time, we recommend to clone and install this repository, so you have all
code and examples at hand:

```
$ pip install -e .
```

Alternatively, you can also install our [latest release](https://pypi.org/project/vessim/) 
via [pip](https://pip.pypa.io/en/stable/quickstart/):

```
$ pip install vessim
```


## 🚀 Getting started

To execute our exemplary co-simulation scenario, run:

```
$ python examples/cosim_example.py
```


### Software-in-the-Loop Simulation

Software-in-the-Loop (SiL) allows Vessim to interact with real computing systems.
There is not yet good documentation on how to set up a full SiL scenario, but you can play with the existing
functionality by installing 

```
pip install vessim[sil]
```

and running:

```
$ python examples/sil_example.py
```


### Vessim Base Components

We are still working on examples for the base modules such as `CarbonApi` or `Generator` which can be used directly
without the use of Mosaik to support simple experiments that do not require the entire co-simulation engine to run.

Documentation and API are in progress.


## 🏗️ Development

Install Vessim with the `dev` option in a virtual environment:

```
python -m venv venv                # create venv
. venv/bin/activate                # activate venv
pip install ".[sil,dev,analysis]"  # install dependencies
```


## 📖 Publications

If you use Vessim in your research, please cite our vision paper:

- Philipp Wiesner, Ilja Behnke and Odej Kao. "[A Testbed for Carbon-Aware Applications and Systems](https://arxiv.org/pdf/2306.09774.pdf)" arXiv:2302.08681 [cs.DC]. 2023.

Bibtex:
```
@misc{vessim2023,
    title={A Testbed for Carbon-Aware Applications and Systems}, 
    author={Wiesner, Philipp and Behnke, Ilja and Kao, Odej},
    year={2023},
    eprint={2306.09774},
    archivePrefix={arXiv},
    primaryClass={cs.DC}
}
```
