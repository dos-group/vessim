# Getting Started

This walkthrough builds a complete Vessim simulation step by step. It covers the four building blocks of every Vessim experiment — **Environment**, **Actors**, **Dispatchables**, and **Controllers** — and ends with an interactive view of the results in your browser.

The final code matches [`examples/basic_example.py`](https://github.com/dos-group/vessim/blob/main/examples/basic_example.py) in the repository, so you can follow along by running that file directly.

## 1. The Environment

The `Environment` manages simulation time and the synchronization between all components. We start by creating one with a step size of 5 minutes (300 s):

```python
import vessim as vs

environment = vs.Environment(sim_start="2022-06-09 00:00:00", step_size=300)
```

We pick June 9, 2022 because that date is covered by the solar dataset we'll use later.

## 2. Actors

**Actors** are the energy consumers and producers in your microgrid. Each actor wraps a [`Signal`](concepts/signals.md) that provides its power value at any point in time.

We start with a server that constantly draws 700 W. By Vessim convention, consumption is negative — passing `consumer=True` flips the sign for us so we can write the power as a positive number:

```python
server = vs.Actor(name="server", signal=vs.StaticSignal(value=700), consumer=True)
```

Next, we add a solar panel. Vessim ships with [several historical datasets](concepts/signals.md#included-datasets); here we use a normalized 2022 trace for Berlin and scale it to a 5 kW peak:

```python
solar = vs.Actor(
    name="solar_panel",
    signal=vs.Trace.load("solcast2022_global", column="Berlin", params={"scale": 5000}),
)
```

At every step, Vessim sums the actors' powers into the microgrid's **power delta** — positive means surplus, negative means deficit.

## 3. Dispatchables

**Dispatchables** are controllable resources whose power is decided at each step by a [`DispatchPolicy`](concepts/dispatchables.md#dispatch-policies). The most common dispatchable is a battery. Vessim's `SimpleBattery` is an ideal capacity-based model:

```python
battery = vs.SimpleBattery(name="battery", capacity=1500, initial_soc=0.8, min_soc=0.3)
```

Without a custom policy, Vessim uses the `DefaultDispatchPolicy` which charges on surplus, discharges on deficit, and exchanges any leftover power with the public grid. See [Dispatchables and Dispatch Policies](concepts/dispatchables.md) for islanded mode, custom policies, and how to model anything beyond batteries.

## 4. Grid Signals (optional)

A microgrid can also carry **grid signals** — time-varying contextual data such as carbon intensity or electricity price. They don't consume or produce power, but custom dispatch policies and controllers can use them to make smarter decisions, and the experiment viewer plots them next to your power flows.

We add carbon intensity from the included WattTime CAISO-North trace. The trace is from 2023, so we shift it forward to our 2022 simulation window via the `start_time` parameter:

```python
grid_signals = {
    "carbon_intensity": vs.Trace.load(
        "watttime2023_caiso-north", params={"start_time": "2022-06-09"}
    ),
}
```

## 5. Putting the microgrid together

`add_microgrid` combines actors, dispatchables, and grid signals into one simulated system. You can call it multiple times to simulate several geo-distributed microgrids in parallel — see [the multi-microgrid section below](#multiple-microgrids).

```python
environment.add_microgrid(
    name="datacenter",
    actors=[server, solar],
    dispatchables=[battery],
    grid_signals=grid_signals,
)
```

## 6. Logging and running

The last ingredient is a **Controller**. Controllers observe the simulation at every step. We use the built-in `CsvLogger`, which writes the experiment configuration and full timeseries to a directory:

```python
environment.add_controller(vs.CsvLogger("results/basic_example"))

environment.run(until=24 * 3600)  # 24 hours
```

After the run, `results/basic_example/` contains:

```
results/basic_example/
  metadata.yaml    # static experiment configuration
  timeseries.csv   # power flows, battery state, grid signals at every step
```

Custom controllers can do much more than logging — they can mutate the dispatch policy at runtime or expose the simulation as a REST API. See [Controllers](concepts/controllers.md) and [Software-in-the-Loop](concepts/sil.md).

## 7. Exploring the results

Vessim ships with a browser-based experiment viewer. Launch it on your results directory:

```console
vessim view results/basic_example
```

This opens an interactive dashboard with charts for power flows, battery state of charge, and grid signals.

You can also [**open the live demo of this exact run**](viewer/index.html){target="_blank"} — it's served as a static page from the documentation site.

## The complete example

```python
import vessim as vs

environment = vs.Environment(sim_start="2022-06-09 00:00:00", step_size=300)

environment.add_microgrid(
    name="datacenter",
    actors=[
        vs.Actor(name="server", signal=vs.StaticSignal(value=700), consumer=True),
        vs.Actor(name="solar_panel", signal=vs.Trace.load(
            "solcast2022_global", column="Berlin", params={"scale": 5000}
        )),
    ],
    dispatchables=[
        vs.SimpleBattery(name="battery", capacity=1500, initial_soc=0.8, min_soc=0.3)
    ],
    grid_signals={
        "carbon_intensity": vs.Trace.load(
            "watttime2023_caiso-north", params={"start_time": "2022-06-09"}
        ),
    },
)

environment.add_controller(vs.CsvLogger("results/basic_example"))
environment.run(until=24 * 3600)
```

## Multiple microgrids

`add_microgrid` can be called more than once. Each microgrid is simulated in parallel and gets its own row in the logged results. This is useful for distributed scenarios — e.g. comparing two data center sites in different regions:

```python
environment.add_microgrid(name="berlin", actors=[...], dispatchables=[...])
environment.add_microgrid(name="munich", actors=[...], dispatchables=[...])
```

## Next steps

- **[Signals and Datasets](concepts/signals.md)** — replay historical data, build constant or custom signals.
- **[Dispatchables and Dispatch Policies](concepts/dispatchables.md)** — battery models, custom dispatchables, custom policies.
- **[Controllers](concepts/controllers.md)** — observe and modify a running simulation.
- **[Software-in-the-Loop](concepts/sil.md)** — connect Vessim to live data sources and real applications.
