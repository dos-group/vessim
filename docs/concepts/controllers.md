# Controllers

A [`Controller`](../api_reference/controller.md) is executed at every simulation step. 
It can observe the state of all microgrids, log it, and modify components of the running simulation, for example by changing parameters of a [`DispatchPolicy`](../api_reference/dispatch_policy.md) on the fly.

Vessim ships with two built-in loggers ([`CsvLogger`](../api_reference/controller.md#vessim.CsvLogger) and [`MemoryLogger`](../api_reference/controller.md#vessim.MemoryLogger)), an [`Api`](../api_reference/controller.md#vessim.Api) controller for software-in-the-loop experiment, and you can write your own by subclassing `Controller`.

## Logging with CsvLogger

[`CsvLogger`](../api_reference/controller.md#vessim.CsvLogger) is the recommended way to record an experiment. It writes the static configuration and the full timeseries to a directory:

```python
environment.add_controller(vs.CsvLogger("results/my_experiment"))
```

After the run, the directory contains:

```
results/my_experiment/
  metadata.yaml    # static experiment configuration
  timeseries.csv   # power flows, battery state, grid signals at every step
```

These two files are exactly what the [experiment viewer](../getting_started.md#7-exploring-the-results) consumes. Open them in your browser with `vessim view results/my_experiment`.

!!! tip "MemoryLogger"
    For interactive exploration in a notebook, use [`vs.MemoryLogger()`](../api_reference/controller.md#vessim.MemoryLogger) instead. It keeps the simulation state in memory and exposes `.to_df()` for direct DataFrame analysis.

## Writing a custom controller

Subclass [`Controller`](../api_reference/controller.md) and implement `step`. Optionally override `start` to grab references to the environment before the simulation begins:

```python
import vessim as vs

class MyController(vs.Controller):
    def start(self, environment):
        # Called once before the simulation starts
        self.microgrids = environment.microgrids

    def step(self, now, microgrid_states):
        # Called at every simulation step
        ...
```

The `step` method receives:

- `now` — the current simulation time as a `datetime`.
- `microgrid_states` — a `dict[str, MicrogridState]` keyed by microgrid name. Each [`MicrogridState`](../api_reference/microgrid.md#vessim.MicrogridState) exposes `p_delta`, `p_grid`, `actor_states`, `dispatch_states`, `policy_state`, and `grid_signals`.

## Example: a scheduled charger

Cheap and clean grid hours are typically at night. Let's force-charge the battery between midnight and 6 AM by mutating the `charge_power` of the dispatch policy at runtime:

```python
import vessim as vs

class ScheduledCharger(vs.Controller):
    """Force-charges storage at 500 W between 00:00 and 06:00."""

    def __init__(self, microgrid_name: str):
        self.microgrid_name = microgrid_name

    def start(self, environment):
        mg = environment.microgrids[self.microgrid_name]
        assert isinstance(mg.policy, vs.DefaultDispatchPolicy)
        self.policy = mg.policy

    def step(self, now, microgrid_states):
        self.policy.charge_power = 500.0 if now.hour < 6 else 0.0
```

Add it to the environment alongside the logger:

```python
environment.add_controller(ScheduledCharger("datacenter"))
environment.add_controller(vs.CsvLogger("results/scheduled"))
```

The same pattern works for any policy parameter: switch between policies, raise/lower a battery's `min_soc`, or react to grid signals exposed via `microgrid_states[name]["grid_signals"]`.

## Going further: real-time control

Custom controllers can also expose the simulation to the outside world. The built-in [`Api`](../api_reference/controller.md#vessim.Api) controller starts a REST server that lets external programs query the state and send control commands while the simulation runs. See [Software-in-the-Loop](sil.md) for the full picture.
