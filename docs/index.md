#

<div style="text-align: center; margin-top: -50px">
    <img alt="Vessim Logo" src="assets/logo.png" width="300" />
</div>

Vessim helps you design and test energy-aware systems. Combine applications, renewable generation, batteries, and a grid connection to understand how your system uses energy and how to improve it.

Vessim is mainly used in two ways:

- **Simulation studies:** find designs and control strategies that reduce energy costs, emissions, or reliance on the grid. Compare battery sizes, explore how workloads can follow renewable generation, and test how your choices hold up under changing conditions.
- **Live experiments:** test energy-aware software with real measurements and running systems. Connect an application to simulated solar panels and batteries, observe how it responds, and refine its behavior before deploying physical infrastructure.

A **digital twin** connects these use cases. Measurements from a running system can inform studies of what could happen next and help evaluate possible changes.

Use the same component models for simulation studies and live experiments. Vessim runs them directly by default and supports connecting external simulators through mosaik in either mode. See [execution and coupling](concepts/execution.md).

## How Vessim Works

Vessim simulates local energy systems, called *microgrids*, that combine loads (such as computing equipment, cooling, or charging) with energy sources, dispatchable resources like batteries, and a connection to the public grid.

![Vessim Overview](assets/vessim_overview.png)

The component models are independent of their execution backend. Multiple microgrids advance together inside one environment. Independent study runs can be distributed across Python worker processes.
A microgrid is composed of three kinds of building blocks:

- [Actors](concepts/signals.md) (red): exogenous consumers and producers whose power is determined by a [`Signal`](api_reference/signal.md). Their sum at each step is the microgrid's *power delta*.
- [Dispatchables](concepts/dispatchables.md) (gray): controllable resources like batteries or generators. A [`DispatchPolicy`](api_reference/dispatch_policy.md) decides how to distribute the power delta across them. Any remainder is exchanged with the public grid.
- [Controllers](concepts/controllers.md) (yellow): observe the simulation each step. Built-in loggers record the state, and custom controllers can adjust dispatch parameters or expose the simulation via APIs.


## Try it now

Head to [Getting Started](getting_started.md) for a step-by-step walkthrough that builds a complete microgrid in a few lines of code.

You can also explore a finished simulation in your browser: [open the Experiment Viewer beta](viewer/index.html){target="_blank"} to see the interactive dashboard for the Getting Started run.


## Installation

Install the [latest release](https://pypi.org/project/vessim/) via [pip](https://pip.pypa.io/en/stable/getting-started/):

```console
pip install vessim
```

For external simulator coupling, install `pip install 'vessim[mosaik]'`. For both integrations use `pip install 'vessim[sil,mosaik]'`.

For [software-in-the-loop](concepts/sil.md) capabilities, install the `sil` extra:

```console
pip install vessim[sil]
```


## Contact

Please reach out via [GitHub Discussions](https://github.com/dos-group/vessim/discussions) in case of questions.
