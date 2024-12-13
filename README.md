# Vessim

[![PyPI version](https://img.shields.io/pypi/v/vessim.svg?color=52c72b)](https://pypi.org/project/vessim/)
![Tests](https://github.com/dos-group/vessim/actions/workflows/linting-and-testing.yml/badge.svg)
[![License](https://img.shields.io/pypi/l/vessim.svg)](https://pypi.org/project/vessim/)
[![Supported versions](https://img.shields.io/pypi/pyversions/vessim.svg)](https://pypi.org/project/vessim/)

Vessim is a versatile **co-simulation testbed for carbon-aware applications and systems** which connects domain-specific simulators for renewable power generation and energy storage with real software and hardware.

It simulates energy systems that interact with real or simulated computing systems for:

- **Carbon-aware applications**: Simulated microgrids offer real-time visibility and control via APIs, enabling the development of novel applications that interact with their energy system.
- **Energy system composition**: Examine how the integration of solar panels, wind energy, or batteries would affect the energy mix of your datacenters.
- **Digital Twins**: Predict future system states in carbon-aware datacenters, aid decision-making, and assess risks during extreme events like power outages.
- **Quality Assurance**: Apply Vessim in continuous integrating testing or use it to validate software roll-outs in a controlled environment.

Vessim can simulate large numbers of microgrids in parallel, comes with ready-to-use datasets, can execute simulated experiments faster than real-time, and is easily extendable with new simulators of any platform through [Mosaik](https://mosaik.offis.de)'s TCP interface.

**Check out the official [documentation](https://vessim.readthedocs.io/en/latest/)!**

## Example scenario

The scenario below simulates a microgrid consisting of a simulated computing system (which consistently draws 400W), a single producer (a solar power plant who's production is modelled based on a dataset provided by [Solcast](https://solcast.com/)), and a battery. The *Monitor* periodically stores the energy system state.

```python
import vessim as vs

environment = vs.Environment(sim_start="2022-06-15")

monitor = vs.Monitor()
environment.add_microgrid(
    actors=[
        vs.ComputingSystem(nodes=[vs.MockSignal(value=400)]),
        vs.Actor(
            name="solar_panel",
            signal=vs.HistoricalSignal.load("solcast2022_global", column="Berlin")
        ),
    ],
    controllers=[monitor],
    storage=vs.SimpleBattery(capacity=100),
    step_size=60,
)

environment.run(until=24 * 3600)  # 24h
monitor.to_csv("result.csv")
```


## Installation

You can install the [latest release](https://pypi.org/project/vessim/) of Vessim
via [pip](https://pip.pypa.io/en/stable/quickstart/):

```
pip install vessim
```

If you require software-in-the-loop (SiL) capabilities, you should additionally install the `sil` extension:

```
pip install vessim[sil]
```

For complex scenarios that involve custom co-simulation actors we recommend cloning and editing this depository directly.


## Work in progress

Our team at the [Distributed and Operating Systems](https://distributedsystems.berlin/) group at TU Berlin is actively working to improve Vessim.
We are currently working on the following aspects and features:

- **Calibration**: We are working on a methodology for calibrating Vessim simulations on real hardware testbeds.
- **System Advisor Model (SAM)**: We are working on integrating NREL's [SAM](https://sam.nrel.gov/) as a subsystem in Vessim, allowing for better simulation of solar arrays, wind farms, and other types of renewable energy generators.
- **Battery degradation**: We are working on integrating NREL's [BLAST-Lite](https://github.com/NREL/BLAST-Lite) for modeling battery lifetime and degradation
- **Vessim X Flower**: We are working on integrating Vessim into the federated learning framework [Flower](https://flower.ai).
- **Software-in-the-loop API**: We will soon release a new API for SiL simulations with new examples and better documentation.


## Datasets

Vessim comes with ready-to-user datasets for solar irradiance and average carbon intensity provided by

<p float="left">
  <img src="docs/_static/solcast_logo.png" width="120" />
  <span> and </span>
  <img src="docs/_static/watttime_logo.png" width="120" />
</p>

We're working on documentation on how to include custom datasets for your simulations.


## Publications

If you use Vessim in your research, please cite our paper:

- Philipp Wiesner, Ilja Behnke, Paul Kilian, Marvin Steinke, and Odej Kao. "[Vessim: A Testbed for Carbon-Aware Applications and Systems.](https://arxiv.org/pdf/2306.09774.pdf)" _3rd Workshop on Sustainable Computer Systems (HotCarbon)_. 2024.

```
@inproceedings{wiesner2024vessim,
    title     = {Vessim: A Testbed for Carbon-Aware Applications and Systems},
    author    = {Wiesner, Philipp and Behnke, Ilja and Kilian, Paul and Steinke, Marvin and Kao, Odej},
    booktitle = {3rd Workshop on Sustainable Computer Systems (HotCarbon)},
    year      = {2024},
}
```

For details in Vessim's software-in-the-loop simulation methodology, refer to our journal paper:

- Philipp Wiesner, Marvin Steinke, Henrik Nickel, Yazan Kitana, and Odej Kao. "[Software-in-the-Loop Simulation for Developing and Testing Carbon-Aware Applications.](https://doi.org/10.1002/spe.3275)" _Software: Practice and Experience, 53 (12)_. 2023.

```
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
```

