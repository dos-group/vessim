# Vessim

[![PyPI version](https://img.shields.io/pypi/v/vessim.svg?color=52c72b)](https://pypi.org/project/vessim/)
![Tests](https://github.com/dos-group/vessim/actions/workflows/linting-and-testing.yml/badge.svg)
[![License](https://img.shields.io/pypi/l/vessim.svg)](https://pypi.org/project/vessim/)
[![Supported versions](https://img.shields.io/pypi/pyversions/vessim.svg)](https://pypi.org/project/vessim/)

Vessim is a versatile **co-simulation testbed for carbon-aware applications and systems** which connects domain-specific simulators for renewable power generation and energy storage with real software and hardware.

## What can I do with it?

Vessim allows you to simulate energy systems next to real or simulated computing systems:

```python
environment = Environment(sim_start="15-06-2022")
environment.add_grid_signal("carbon_intensity", TimeSeriesApi.from_dataset("carbon_data1"))

monitor = Monitor(step_size=60)  # stores simulation state every 60s
environment.add_microgrid(Microgrid(
    actors=[
        # Single server which always draws 100W
        ComputingSystem(
            name="server",
            step_size=60,
            power_meters=[MockPowerMeter(name="pm", p=100)]
        ),
        # Solar panel simulated according to real historical solar data provided by Solcast
        Generator(
            name="solar",
            step_size=60,
            time_series_api=TimeSeriesApi.from_dataset("solcast2022_global"))
        ),
    ],
    controllers=[monitor],
    storage=SimpleBattery(capacity=500000, charge_level=200000, min_soc=.6),
    zone="DE",
))

environment.run(until=24*3600)  # 24h
monitor.monitor_log_to_csv(result_csv)
```


## Installation

You can install the [latest release](https://pypi.org/project/vessim/) of Vessim 
via [pip](https://pip.pypa.io/en/stable/quickstart/):

```
pip install vessim
```

For more complex scenarios that involve custom co-simulation actors we recomend cloning this depository directly.


## Work in progress

Our team at the [Distributed and Operating Systems](https://distributedsystems.berlin/) group at TU Berlin is actively working to improve Vessim.
We are currently working on the following aspects and features:

- **Better documentation**: You can find the current WiP documentation [here](https://vessim.readthedocs.io/en/latest/)
- **Software-in-the-loop (SiL) capabilities**: The current SiL implementation is focussed around our exemplary use case presented in our [journal paper](https://doi.org/10.1002/spe.3275). We are working on a SiL interface for users to implement custom interfaces for the communication of computing and energy systems.
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
