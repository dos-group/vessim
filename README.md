# Vessim

[![PyPI version](https://img.shields.io/pypi/v/vessim.svg?color=52c72b)](https://pypi.org/project/vessim/)
![Build](https://github.com/dos-group/vessim/actions/workflows/vessim-ci.yml/badge.svg)
[![License](https://img.shields.io/pypi/l/vessim.svg)](https://pypi.org/project/vessim/)
[![Supported versions](https://img.shields.io/pypi/pyversions/vessim.svg)](https://pypi.org/project/vessim/)

Vessim is a versatile co-simulation testbed for carbon-aware applications and systems.
It lets users connect domain-specific simulators for energy system components like renewable power generation, 
energy storage, and power flow analysis with real software and hardware.

Vessim is in alpha stage and under active development.
Functionality and documentation will improve in the next weeks an months.


## ⚙️ Installation

You can install the [latest release](https://pypi.org/project/vessim/) of Vessim via [pip](https://pip.pypa.io/en/stable/quickstart/):

```
$ pip install vessim
```


## 🚀 Getting started

Vessim uses [Mosaik](https://mosaik.offis.de/) for co-simulation.
To run the example scenario, clone the repository (including all examples) and set up your environment via:

```
$ pip install -e .
```

To execute the fully simulated example scenario, run:
```
$ python examples/scenario_1.py
```


# Development

Install the requirements in a virtual environment:

```
python3 -m venv venv              # create venv
. venv/bin/activate               # activate venv
pip3 install -r requirements.txt  # install dependencies
```

Install & start docker `systemctl start docker`
