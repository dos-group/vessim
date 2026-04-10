#

<div style="text-align: center; margin-top: -50px">
    <img alt="Vessim Logo" src="assets/logo.png" width="300" />
</div>

Vessim is a **co-simulation testbed for computing and energy systems**.

Vessim lets you simulate the interaction of real or simulated computing systems with on-site energy sources, storage, and the public grid.
It connects domain-specific simulators for power generation and batteries with real software and hardware.


## What can I do with Vessim?

Vessim helps you to understand and optimize how your (distributed) computing system interacts with (distributed) energy sources and battery storage.

- **Energy-aware applications**: Develop applications that adapt their energy consumption to the carbon intensity and price of electricity.
- **Microgrid composition**: Experiment with adding solar panels, wind turbines, or batteries to see how they would affect your energy costs and carbon emissions.
- **Demand response and power outages**: Simulate demand response signals or power outages to understand your system's flexibility and test mitigation strategies.
- **Quality assurance**: Apply Vessim in continuous integrating testing to validate software roll-outs in a controlled environment.

Vessim can simulate multiple distributed microgrids in parallel and easily integrates historical datasets and new simulators. 

Vessim’s software-in-the-loop capabilities let you run real systems against simulated microgrids. Connect live data sources like Prometheus and interact through REST APIs.


## How Vessim Works

Vessim simulates local energy systems, called **microgrids**, that combine computing equipment with (renewable) energy sources, dispatchable resources like batteries, and a connection to the public grid.

![Vessim Overview](assets/vessim_overview.png)

Vessim is based on [Mosaik](https://mosaik.offis.de), a general-purpose co-simulation framework.
In the diagram, all hexagons represent a distinct Mosaik component which can be either simulated or real (software-in-the-loop).
Vessim has the following core components:

- **Actors** (red): Exogenous energy consumers and producers whose power output is determined by an underlying [Signal](tutorials/2_signals_and_datasets.md).
    - Computing systems (servers, workstations, etc.) that consume power
    - Energy sources (solar panels, wind turbines) that produce power
    - Signals can be static, based on historical traces, or fed from real-time sources like Prometheus

    At each simulation step, the **Grid** sums all actor powers to compute the net surplus or deficit of the microgrid.

- **Dispatchables** (gray): Controllable energy resources whose power output is managed by a `DispatchPolicy`.
    - The most common dispatchable is a battery, but anything with a controllable power setpoint (diesel generators, hydrogen electrolyzers, etc.) can be modeled as a `Dispatchable`.
    - Vessim ships with two battery models: `SimpleBattery` (ideal, capacity-based) and `ClcBattery` (a realistic lithium-ion model based on [Kazhamiaka et al., 2019](https://doi.org/10.1186/s42162-019-0070-6)).
    - The `DispatchPolicy` decides how to distribute the power delta across dispatchables. The default policy charges batteries when there is excess power and discharges them during deficits. Any remaining imbalance is exchanged with the public grid. You can implement custom policies for more advanced strategies (e.g., charging only when the grid is clean).

- **Controllers** (yellow): Observe and interact with the simulation at every step.
    - Built-in loggers (`MemoryLogger`, `CsvLogger`) record the experiment metadata as well as full microgrid state over time
    - The `Api` controller exposes a REST API for real-time monitoring and control, as well as Prometheus metrics.
    - You can implement custom controllers to, e.g., adjust dispatch policy parameters based on electricity prices.


## Installation

You can install our [latest release](https://pypi.org/project/vessim/) via [pip](https://pip.pypa.io/en/stable/getting-started/):

```console
pip install vessim
```

If you require software-in-the-loop capabilities (e.g. loading live data from Prometheus and/or exposing the simulated microgrids via a REST API), you can install the `sil` extra:

```console
pip install vessim[sil]
```
