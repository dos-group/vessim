# Overview

Vessim is a **co-simulation testbed for carbon-aware systems** that allows you to simulate how your computing systems interact with local renewable energy sources, battery storage, and the public grid.
It connects domain-specific simulators for power generation and energy storage with **real software and hardware**.

<div style="text-align: center;">
    <img alt="Vessim Logo" src="assets/logo.png" width="250" />
</div>

## What can I do with Vessim?

Vessim helps you to understand and optimize how your (distributed) computing system interacts with (distributed) renewable energy sources and battery storage.

- **Carbon-aware applications**: Develop applications that automatically reduce their energy consumption when the grid is powered by fossil fuels, and increase activity when renewable energy is abundant.
- **Energy system composition**: Experiment with adding solar panels, wind turbines, or batteries to see how they would affect your energy costs and carbon emissions.
- **Plan for outages and extreme events**: Simulate power outages or renewable energy fluctuations to understand risks and test backup strategies.
- **Quality assurance**: Apply Vessim in continuous integrating testing to validate software roll-outs in a controlled environment.

Vessim is based on [Mosaik](https://mosaik.offis.de), a general-purpose co-simulation framework.
It can simulate large numbers of microgrids in parallel, comes with ready-to-use datasets, can execute simulated experiments faster than real-time, and is easily extendable with new simulators of any platform through Mosaik's TCP interface.
You can **connect Vessim to real-world applications and hardware**, enabling software-in-the-loop (SiL) testing.

## Installation

You can install our [latest release](https://pypi.org/project/vessim/) via [pip](https://pip.pypa.io/en/stable/getting-started/):

```console
pip install vessim
```

If you require software-in-the-loop capabilities (e.g. loading live data from Prometheus and/or exposing the simulated microgrids via a REST API), you can install the `sil` extra:

```console
pip install vessim[sil]
```


## How Vessim Works

Vessim simulates local energy systems called **microgrids** that combine computing equipment with renewable energy sources, controllable resources like batteries, and a connection to the public grid.

![Vessim Overview](assets/vessim_overview.png)

In the diagram, all hexagons represent a distinct [Mosaik](https://mosaik.offis.de) component which can be either simulated or real (software-in-the-loop).
Vessim has the following core components:

- **Actors** (red): Exogenous energy consumers and producers whose power output is determined by an underlying [Signal](tutorials/2_signals_and_datasets.md).
    - Computing systems (servers, workstations, etc.) that consume power
    - Renewable sources (solar panels, wind turbines) that produce power
    - Signals can be static, based on historical traces, or fed from real-time sources like Prometheus

    At each simulation step, the **Grid** sums all actor powers to compute the **power delta** — the net surplus or deficit of the microgrid.

- **Dispatchables** (gray): Controllable energy resources whose power output is managed by a **Dispatch Policy**.
    - The most common dispatchable is a battery, but anything with a controllable power setpoint (diesel generators, hydrogen electrolyzers, etc.) can be modeled as a `Dispatchable`.
    - Vessim ships with two battery models: `SimpleBattery` (ideal, capacity-based) and `ClcBattery` (a realistic lithium-ion model based on [Kazhamiaka et al., 2019](https://doi.org/10.1186/s42162-019-0070-6)).
    - The **Dispatch Policy** decides how to distribute the power delta across dispatchables. The default policy charges batteries when there is excess power and discharges them during deficits. Any remaining imbalance is exchanged with the public grid. You can implement custom policies for more advanced strategies (e.g., charging only when the grid is clean).

- **Controllers** (yellow): Observe and interact with the simulation at every step.
    - Built-in loggers (`MemoryLogger`, `CsvLogger`) record the full microgrid state over time
    - The `Api` controller exposes a REST API for real-time monitoring and control
    - You can implement custom controllers to, e.g., adjust dispatch policy parameters based on grid carbon intensity
