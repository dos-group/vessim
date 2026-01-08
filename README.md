# Vessim

[![PyPI version](https://img.shields.io/pypi/v/vessim.svg?color=52c72b)](https://pypi.org/project/vessim/)
![Tests](https://github.com/dos-group/vessim/actions/workflows/lint-and-unit-test.yml/badge.svg)
[![License](https://img.shields.io/pypi/l/vessim.svg)](https://pypi.org/project/vessim/)
[![Supported versions](https://img.shields.io/pypi/pyversions/vessim.svg)](https://pypi.org/project/vessim/)

Vessim is a **co-simulation testbed for carbon-aware systems** that allows you to simulate how your computing systems interact with local renewable energy sources, battery storage, and the public grid.
It connects domain-specific simulators for power generation and energy storage with **real software and hardware**.


## What can I do with Vessim?

Vessim helps you to understand and optimize how your (distributed) computing system interacts with (distributed) renewable energy sources and battery storage.

- **Carbon-aware applications**: Develop applications that automatically reduce their energy consumption when the grid is powered by fossil fuels, and increase activity when renewable energy is abundant.
- **Energy system composition**: Experiment with adding solar panels, wind turbines, or batteries to see how they would affect your energy costs and carbon emissions.
- **Plan for outages and extreme events**: Simulate power outages or renewable energy fluctuations to understand risks and test backup strategies.
- **Quality assurance**: Apply Vessim in continuous integrating testing to validate software roll-outs in a controlled environment.

Vessim can run simulations faster than real-time, includes historical datasets for realistic scenarios, and can simulate multiple microgrids in parallel. 
You can test scenarios using historical data or connect real applications and hardware to simulated energy systems.

**Check out the official [documentation](https://vessim.readthedocs.io/en/latest/)!**


## Simple scenario

The scenario below simulates a microgrid consisting of a simulated computing system (which consistently draws 700W), 
a single producer (a solar power plant who's production is modelled based on a dataset provided by [Solcast](https://solcast.com/)), and a battery. 
The *Monitor* periodically stores the energy system state in a CSV file.

```python
import vessim as vs

environment = vs.Environment(sim_start="2022-06-15", step_size=300)  # 5 minute step size

microgrid = environment.add_microgrid(
    name="datacenter",
    actors=[
        vs.Actor(name="server", signal=vs.StaticSignal(value=-700)),  # negative = consumes power
        vs.Actor(name="solar_panel", signal=vs.Trace.load("solcast2022_global", column="Berlin", params={"scale": 5000})),  # 5kW maximum
    ],
    storage=vs.SimpleBattery(capacity=100),
)

# Write results to CSV
environment.add_controller(vs.CsvLogger("./results.csv"))

environment.run(until=24 * 3600)  # 24h simulated time
```

You can find this and more executable examples in the [`examples/`](examples/) directory.


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


## Datasets

Vessim comes with ready-to-user datasets for solar irradiance and average carbon intensity provided by

<p float="left">
  <img src="docs/assets/solcast_logo.png" width="120" />
  <span> and </span>
  <img src="docs/assets/watttime_logo.png" width="120" />
</p>

We're working on documentation on how to include custom datasets for your simulations.


## Publications

If you use Vessim in your research, please cite our paper:

- Philipp Wiesner, Ilja Behnke, Paul Kilian, Marvin Steinke, and Odej Kao. "[Vessim: A Testbed for Carbon-Aware Applications and Systems.](https://dl.acm.org/doi/pdf/10.1145/3727200.3727210)" _ACM SIGENERGY Energy Informatics Review 4 (5)_. 2024.

For details in Vessim's software-in-the-loop simulation methodology, refer to:

- Philipp Wiesner, Marvin Steinke, Henrik Nickel, Yazan Kitana, and Odej Kao. "[Software-in-the-Loop Simulation for Developing and Testing Carbon-Aware Applications.](https://doi.org/10.1002/spe.3275)" _Software: Practice and Experience, 53 (12)_. 2023.

For BibTeX citations and more related papers, please refer to the [documentation](https://vessim.readthedocs.io/en/latest/about.html#publications).
