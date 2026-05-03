# Getting Started

This walkthrough builds a complete Vessim simulation step by step.

The final code matches [`examples/basic_example.py`](https://github.com/dos-group/vessim/blob/main/examples/basic_example.py) in the repository, so you can follow along by running that file directly.

## 1. The Environment

The [`Environment`](api_reference/environment.md) manages simulation time and the synchronization between all components. We start by creating one with a step size of 5 minutes (300 seconds):

```python
import vessim as vs

environment = vs.Environment(sim_start="2026-05-03", step_size=300)
```

Vessim has two modes:

- *simulated* (used here) uses only simulated actors and runs as fast as possible (see [Discrete-event simulation](https://en.wikipedia.org/wiki/Discrete-event_simulation) on Wikipedia). The `sim_start` parameter labels the output (e.g. CSV timestamps).
- *live* (via [`Environment.live`](api_reference/environment.md#vessim.Environment.live)) advances at wall-clock speed and can connect to real systems, see [Software-in-the-Loop](concepts/sil.md). Here, `sim_start` is optional and defaults to `datetime.now()`.

## 2. Actors

Actors are the energy consumers and producers in your microgrid. 
Each actor wraps a [`Signal`](concepts/signals.md) that provides its power value at any point in time.

We start with a server that constantly draws 700 W. 
By Vessim convention, production yields positives and consumption negative values. 
Passing `consumer=True` flips the sign of the singal:

```python
server = vs.Actor(name="server", signal=vs.StaticSignal(value=700), consumer=True)
```

Next, we add a solar panel. We point it at a CSV from the repository's `datasets/` directory, pick the Berlin column, and scale the normalized data to a 5 kW peak:

```python
solar = vs.Actor(
    name="solar_panel",
    signal=vs.Trace.from_csv(
        "datasets/solar_example.csv",
        column="Berlin",
        scale=5000,
    ),
)
```

A [`Trace`](api_reference/signal.md#vessim.Trace) replays a CSV row-by-row, indexed by an offset in seconds since the trace's start. See [Signals and Datasets](concepts/signals.md) for all available signal types, the CSV schema, and how to fetch more data.

At every step, Vessim sums the actors' powers into the microgrid's *power delta*. Again, positive means surplus, negative means deficit.

## 3. Dispatchables (optional)

Dispatchables are controllable resources whose power is decided at each step by a [`DispatchPolicy`](api_reference/dispatch_policy.md). The most common dispatchable is a battery. Vessim's [`SimpleBattery`](api_reference/dispatchable.md#vessim.SimpleBattery) is an ideal capacity-based model:

```python
battery = vs.SimpleBattery(name="battery", capacity=1500, initial_soc=0.8, min_soc=0.3)
```

Without a custom policy, Vessim uses the [`DefaultDispatchPolicy`](api_reference/dispatch_policy.md#vessim.DefaultDispatchPolicy) which charges on surplus, discharges on deficit, and exchanges any leftover power with the public grid. See [Dispatchables and Dispatch Policies](concepts/dispatchables.md) for islanded mode, custom policies, and how to model anything beyond batteries.

## 4. Grid Signals (optional)

A microgrid can also carry *grid signals*: time-varying contextual data such as local electricity price or carbon intensity.
They don't consume or produce power, but custom dispatch policies and controllers can use them to make decisions.

We add carbon intensity from a WattTime CAISO-North trace. 
This CSV is datetime-indexed, so we pass an `anchor=` to mark which row maps to our simulation start with offset=0:

```python
grid_signals = {
    "carbon_intensity": vs.Trace.from_csv(
        "datasets/watttime_example.csv",
        anchor="2023-06-08 00:00:00",
    ),
}
```

## 5. Putting the microgrid together

[`add_microgrid`](api_reference/environment.md#vessim.Environment.add_microgrid) combines actors, dispatchables, and grid signals into one simulated system. 
You can call it multiple times to simulate several geo-distributed microgrids in parallel.

```python
environment.add_microgrid(
    name="datacenter",
    actors=[server, solar],
    dispatchables=[battery],
    grid_signals=grid_signals,
)
```

## 6. Logging and running

The last ingredient is a [`Controller`](api_reference/controller.md). 
Controllers observe the simulation at every step and can react to it.
We use the built-in [`CsvLogger`](api_reference/controller.md#vessim.CsvLogger), which writes the experiment configuration and full timeseries to a directory:

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

Custom controllers can do much more than logging: they can mutate the dispatch policy at runtime or expose the simulation as a REST API. See [Controllers](concepts/controllers.md) and [Software-in-the-Loop](concepts/sil.md).

## 7. Exploring the results

Vessim ships with a browser-based experiment viewer. Launch it on your results directory:

```console
vessim view results/basic_example
```

This opens an interactive dashboard with charts for power flows, battery state of charge, and grid signals.

You can also [open the live demo of this exact run](viewer/index.html){target="_blank"}, served as a static page from the documentation site.

## The complete example

```python
import vessim as vs

environment = vs.Environment(sim_start="2022-06-09", step_size=300)

environment.add_microgrid(
    name="datacenter",
    actors=[
        vs.Actor(name="server", signal=vs.StaticSignal(value=700), consumer=True),
        vs.Actor(name="solar_panel", signal=vs.Trace.from_csv(
            "datasets/solar_example.csv", column="Berlin", scale=5000
        )),
    ],
    dispatchables=[
        vs.SimpleBattery(name="battery", capacity=1500, initial_soc=0.8, min_soc=0.3)
    ],
    grid_signals={
        "carbon_intensity": vs.Trace.from_csv(
            "datasets/watttime_example.csv", anchor="2023-06-08 00:00:00"
        ),
    },
)

environment.add_controller(vs.CsvLogger("results/basic_example"))
environment.run(until=24 * 3600)
```


## Next steps

- [Signals and Datasets](concepts/signals.md) — replay historical data, build constant or custom signals.
- [Dispatchables and Dispatch Policies](concepts/dispatchables.md) — battery models, custom dispatchables, custom policies.
- [Controllers](concepts/controllers.md) — observe and modify a running simulation.
- [Software-in-the-Loop](concepts/sil.md) — connect Vessim to live data sources and real applications.
