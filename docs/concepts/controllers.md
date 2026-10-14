# Controllers

A [`Controller`](../api_reference/controller.md) is executed at every simulation step. 
It can observe the state of all microgrids, log it, and modify components of the running simulation, for example by changing parameters of a [`DispatchPolicy`](../api_reference/dispatch_policy.md) on the fly.

All built-in controllers use the same `start`, `step`, and `finalize` interface. Choose them according to what you need from a run:

| Controller | Purpose | What it retains or exposes |
|---|---|---|
| [`Summary`](../api_reference/controller.md#vessim.Summary) | Compare the outcomes of many scenarios | Grid import/export energy and peak power, with optional JSON output at completion |
| [`MemoryLogger`](../api_reference/controller.md#vessim.MemoryLogger) | Analyze a run in Python or a notebook | Every tick in memory, accessible as a dictionary or DataFrame |
| [`CsvLogger`](../api_reference/controller.md#vessim.CsvLogger) | Save a detailed run and open it in the viewer | Every tick in a CSV file, plus experiment metadata |
| [`Api`](../api_reference/controller.md#vessim.Api) | Interact with a running experiment | Current state and control commands over HTTP |

`Summary` is an ordinary controller that updates a few counters at each tick. It does not retain the observations it receives. The loggers remain useful when you need to see when and why something happened. You can combine controllers, or implement your own metrics and control logic by subclassing `Controller`.

## Compact results for studies

For configuration sweeps and Monte Carlo studies, retain aggregate results rather than full trajectories:

```python
summary = environment.add_controller(vs.Summary("results/summary.json"))
result = environment.run(until=86400)
print(summary.metrics)
```

The JSON file is optional and is written only on finalization. `metrics` contains grid import/export energy in Wh and peak import/export power in W for each microgrid. The final interval is clipped to the requested horizon. Failed or interrupted runs are labeled as partial. Custom metrics such as cost or emissions belong in an ordinary `Controller`. Their units and treatment of imports/exports depend on the experiment.

`run()` itself retains only the final observation. `Summary` retains a fixed number of counters per microgrid. `MemoryLogger` retains every tick and therefore grows with run length.

## Logging with CsvLogger

Use [`CsvLogger`](../api_reference/controller.md#vessim.CsvLogger) when you want to save a detailed trajectory. It writes the static configuration and the full timeseries to a directory:

```python
environment.add_controller(vs.CsvLogger("results/my_experiment"))
```

The logger keeps one buffered file open. In study mode it flushes on close. In live mode it flushes each tick. Pass `flush=True` or `flush=False` to override this. All microgrids share a column union determined at the first tick. Later schema changes raise an error.

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

- `now`: the current simulation time as a `datetime`.
- `microgrid_states`: a `dict[str, MicrogridState]` keyed by microgrid name. Each [`MicrogridState`](../api_reference/microgrid.md#vessim.MicrogridState) exposes `p_delta`, `p_grid`, `actor_states`, `dispatch_states`, `policy_state`, and `grid_signals`.

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

Observations are detached from component state. Treat them as read-only. Controller actions take effect in subsequent computation. Controllers start after scenario preparation and are finalized on completion, errors, and interruption.

Custom controllers can also expose the simulation to the outside world. The built-in [`Api`](../api_reference/controller.md#vessim.Api) controller starts a REST server that lets external programs query the state and send control commands while the simulation runs. See [Software-in-the-Loop](sil.md) for the full picture.
