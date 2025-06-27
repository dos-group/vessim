# Vessim

[![PyPI version](https://img.shields.io/pypi/v/vessim.svg?color=52c72b)](https://pypi.org/project/vessim/)
![Tests](https://github.com/dos-group/vessim/actions/workflows/lint-and-unit-test.yml/badge.svg)
[![License](https://img.shields.io/pypi/l/vessim.svg)](https://pypi.org/project/vessim/)
[![Supported versions](https://img.shields.io/pypi/pyversions/vessim.svg)](https://pypi.org/project/vessim/)

Vessim is a **co-simulation testbed for carbon-aware applications and systems** which connects domain-specific simulators for renewable power generation and energy storage with real software and hardware.

Use Vessim to:

- **Test carbon-aware applications**: Develop software that automatically reduces energy consumption when the grid runs on fossil fuels and increases activity when renewable energy is abundant.
- **Optimize energy infrastructure**: Experiment with adding solar panels, wind turbines, or batteries to see how they would affect your energy costs and carbon emissions.
- **Plan for extreme events**: Simulate power outages or renewable energy fluctuations to understand risks and test backup strategies.
- **Validate software changes**: Test how new deployments or configuration changes will affect energy consumption before rolling them out to production.

Vessim can run simulations faster than real-time, includes historical datasets for realistic scenarios, and can simulate multiple microgrids in parallel. 
You can test scenarios using historical data or connect real applications and hardware to simulated energy systems.

**Check out the official [documentation](https://vessim.readthedocs.io/en/latest/)!**


## Example scenario

The scenario below simulates a microgrid consisting of a simulated computing system (which consistently draws 700W), a single producer (a solar power plant who's production is modelled based on a dataset provided by [Solcast](https://solcast.com/)), and a battery. 
The *Monitor* periodically stores the energy system state in a CSV file.

```python
import vessim as vs

environment = vs.Environment(sim_start="2022-06-15")
environment.add_microgrid(
    actors=[
        vs.Actor(vs.ConstantSignal(value=-700), name="server"),  # negative = consumes power
        vs.Actor(vs.Trace.load("solcast2022_global", column="Berlin"), name="solar_panel", params={"scale": 5000}),  # 5kW maximum
    ],
    controllers=[vs.Monitor(outfile="result.csv")],
    storage=vs.SimpleBattery(capacity=100),
    step_size=300,  # 5 minute step size
)
environment.run(until=24 * 3600)  # 24h
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

For complex scenarios that involve custom co-simulation actors we recommend cloning and editing this depository directly, e.g. via:

```
uv pip install -e ".[dev,sil]"
```


## Work in progress

Our team at the [Distributed and Operating Systems](https://distributedsystems.berlin/) group at TU Berlin is actively working to improve Vessim.
We are currently working on the following aspects and features:

- **Calibration**: We are working on a methodology for calibrating Vessim simulations on real hardware testbeds.
- **System Advisor Model (SAM)**: We are working on integrating NREL's [SAM](https://sam.nrel.gov/) as a subsystem in Vessim, allowing for better simulation of solar arrays, wind farms, and other types of renewable energy generators.
- **Battery degradation**: We are working on integrating NREL's [BLAST-Lite](https://github.com/NREL/BLAST-Lite) for modeling battery lifetime and degradation
- **Vessim X Flower**: We are working on integrating Vessim into the federated learning framework [Flower](https://flower.ai).
- **Vessim X Vidur**: We are working on integrating Vessim into the LLM simulator [Vidur](https://github.com/microsoft/vidur).
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

For details in Vessim's software-in-the-loop simulation methodology, refer to our journal paper:

- Philipp Wiesner, Marvin Steinke, Henrik Nickel, Yazan Kitana, and Odej Kao. "[Software-in-the-Loop Simulation for Developing and Testing Carbon-Aware Applications.](https://doi.org/10.1002/spe.3275)" _Software: Practice and Experience, 53 (12)_. 2023.

For BibTeX citations and more related papers, please refer to the [documentation](https://vessim.readthedocs.io/en/latest/about.html#publications).
