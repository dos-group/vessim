# Vessim

[![PyPI version](https://img.shields.io/pypi/v/vessim.svg?color=52c72b)](https://pypi.org/project/vessim/)
![Tests](https://github.com/dos-group/vessim/actions/workflows/linting-and-testing.yml/badge.svg)
[![License](https://img.shields.io/pypi/l/vessim.svg)](https://pypi.org/project/vessim/)
[![Supported versions](https://img.shields.io/pypi/pyversions/vessim.svg)](https://pypi.org/project/vessim/)

Vessim is a versatile **co-simulation testbed for carbon-aware applications and systems** which connects domain-specific simulators for renewable power generation and energy storage with real software and hardware.

## What can I do with it?

Vessim allows you to simulate energy systems next to real or simulated computing systems:

```python
from vessim.actor import ComputingSystem, Generator
from vessim.controller import Monitor
from vessim.cosim import Environment, Microgrid
from vessim.power_meter import MockPowerMeter
from vessim.signal import HistoricalSignal
from vessim.storage import SimpleBattery

environment = Environment(sim_start="15-06-2022")
environment.add_grid_signal("carbon_intensity", HistoricalSignal.from_dataset("carbon_data1"))

monitor = Monitor()
microgrid = Microgrid(
    actors=[
        ComputingSystem(power_meters=[MockPowerMeter(p=100)]),
        Generator(signal=HistoricalSignal.from_dataset("solcast2022_global")),
    ],
    controllers=[monitor],
    storage=SimpleBattery(capacity=100),
    zone="DE",
    step_size=60,
)
environment.add_microgrid(microgrid)

environment.run(until=24 * 3600)  # 24h
monitor.to_csv("result.csv")
```


## Installation

You can install the [latest release](https://pypi.org/project/vessim/) of Vessim 
via [pip](https://pip.pypa.io/en/stable/quickstart/):

```
pip install vessim
```

If you require software-in-the-loop (SiL) capabilities, you can install the `sil` extra:

```
pip install vessim[sil]
```

For complex scenarios that involve custom co-simulation actors we recommend cloning and editing this depository directly.


## Datasets

Vessim comes with ready-to-user datasets for solar irradiance and average carbon intensity provided by

<p float="left">
  <img src="docs/_static/solcast_logo.png" width="150" />
  <span> and </span>
  <img src="docs/_static/watttime_logo.png" width="150" />
</p>

We're working on documentation on how to include custom datasets for your simulations.


## Work in progress

Our team at the [Distributed and Operating Systems](https://distributedsystems.berlin/) group at TU Berlin is actively working to improve Vessim.
We are currently working on the following aspects and features:

- **Website**: We are currently working on better examples and documentation. You can find the current WiP documentation [here](https://vessim.readthedocs.io/en/latest/).
- **Imroved Software-in-the-loop (SiL) API**: We will soon release a new API for SiL simulations with new examples and better documentation.
- **System Advisor Model (SAM)**: We are working on making NREL's [SAM](https://sam.nrel.gov/) available as a subsystem in Vessim.


## Publications

If you use Vessim in your research, please cite our vision paper:

- Philipp Wiesner, Ilja Behnke and Odej Kao. "[A Testbed for Carbon-Aware Applications and Systems](https://arxiv.org/pdf/2306.09774.pdf)" arXiv:2302.08681 [cs.DC]. 2023.
<details>
    <summary>Bibtex</summary>
    
    @misc{wiesner2023vessim,
        title={A Testbed for Carbon-Aware Applications and Systems}, 
        author={Wiesner, Philipp and Behnke, Ilja and Kao, Odej},
        year={2023},
        eprint={2306.09774},
        archivePrefix={arXiv},
        primaryClass={cs.DC}
    }
</details>

Or our journal paper on software-in-the-loop similation for carbon-aware applications:
- Philipp Wiesner, Marvin Steinke, Henrik Nickel, Yazan Kitana, and Odej Kao. "[Software-in-the-Loop Simulation for Developing and Testing Carbon-Aware Applications](https://doi.org/10.1002/spe.3275)" Software: Practice and Experience, 53 (12). 2023.
<details>
    <summary>Bibtex</summary>
    
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
    
</details>
