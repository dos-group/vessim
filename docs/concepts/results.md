# Recording experiments and metrics

`Recorder` uses one experiment format for simulation studies and live experiments.
Metrics and time series are both enabled by default:

```python
recorder = env.add_controller(vs.Recorder("results/experiment"))
run = env.run(until=86400)
result = recorder.result
print(result.metrics["microgrids"]["site"]["grid_import"])
```

`env.run()` returns the compact execution result and final observation. The recorder's
`ExperimentResult` contains configuration, user parameters, execution status, metrics,
and a reference to the trajectory. Both native and mosaik runs use this format.

## Storage and retention

With an output directory, a run produces:

```text
experiment/
    experiment.json    # configuration, execution, parameters, metrics, definitions
    timeseries.csv     # optional detailed observations
```

The CSV streams to a buffered file and is not also retained in memory. Studies write
the JSON record once on finalization. Live experiments publish the record and flush
the CSV each tick by default. Use `flush=True` or `flush=False` to override this.
Custom metrics are finalized at the end of the run. Their values are null until then.

Without an output directory, the recorder keeps observations in memory. Use
`recorder.to_df()` to obtain a DataFrame indexed by time and microgrid. The same
method explicitly reads the CSV when output is on disk. `recorder.log` exposes the
in-memory observations. It is empty when recording to disk or disabling time series.
In-memory observations are never embedded in experiment JSON: `result.save()` saves
only their summary. Supply an output directory to `Recorder` to persist CSV alongside
the summary, or use `recorder.to_df().to_csv(...)` for a separate table export.

For large studies, disable time series:

```python
recorder = env.add_controller(vs.Recorder(
    timeseries=False,
    run_id="scenario-42",
    parameters={"seed": 42, "battery_capacity_wh": 1500},
))
env.run(until=86400)
record = recorder.result.to_dict()
```

Built-in metrics retain a fixed number of counters per actor and microgrid. Custom
metrics are responsible for their own retention. `metrics=False` disables the
standard physical metrics without disabling custom metrics or time series.

A recorder is single-use. Construct a fresh one, including fresh mutable custom
metric instances, for each scenario. Use a separate output directory for each
concurrent run. Reusing a directory replaces its record and enabled CSV output.

## Default physical metrics

| Scope | Metric | Unit |
|---|---|---|
| Actor and microgrid | `energy_produced`, `energy_consumed` | Wh |
| Microgrid | `grid_import`, `grid_export` | Wh |
| Microgrid | `peak_grid_import`, `peak_grid_export` | W |

Production and consumption are separate nonnegative quantities. Microgrid production
and consumption are sums of the actor quantities, preserving simultaneous generation
and consumption. They exclude dispatchables and external mosaik power inputs.
Grid exchange includes the effects of dispatch and external inputs.

Actor energy uses the sampled power that drives dispatch, including `consumer=True`
and sample holding. It does not infer energy from arbitrary custom diagnostic state.
Energy is power integrated over recorded intervals, with the final interval clipped
to the requested horizon. Peak power is the maximum sampled value, not a rolling
billing demand. Production is not automatically classified as renewable.

Execution information is stored separately in `result.execution`, including `steps`,
`simulated_duration` in seconds, `wall_time` in seconds, `until`, `last_time`, and
`status`. `until` is null for an unbounded live experiment. Execution timing covers
the recorder's lifecycle, including cleanup. The environment's `RunResult.wall_time`
covers the full run. Final records are published after all controllers, signals,
and backend resources have been finalized, so cleanup failures are reflected in
the saved status. An interrupted run retains its interrupted status.

On failure or interruption, retained metrics describe intervals already processed by
the recorder. A tick's interval is counted when that observation is received, including
its remaining time if the live run is interrupted before the next tick. This is a
sampled-model integral, not a meter of actual elapsed wall-clock consumption.

## Scoped values and definitions

Values are ordinary numbers, with definitions in a separate, matching structure:

```python
result.metrics["run"]["capex"]
result.metrics["microgrids"]["site"]["grid_import"]
result.metrics["actors"]["site"]["server"]["energy_consumed"]

result.metric_definitions["microgrids"]["site"]["grid_import"]["unit"]  # Wh
```

Each custom definition includes a unit, description, and assumptions. A dimensionless
ratio uses unit `"1"`. Undefined values, such as a ratio with a zero denominator,
should be None and are saved as JSON null. Nonfinite numeric results are rejected.
A failed metric finalizer leaves its value null and propagates the error after
attempting the other finalizers. A previously successful run becomes failed; an
interrupted run retains its interrupted status.

## Price and emissions calculators

These are opt-in metrics with explicitly selected grid signals:

```python
recorder = env.add_controller(vs.Recorder(custom_metrics={
    "electricity_import_cost": vs.ElectricityImportCost("site", "buy_price", currency="EUR"),
    "electricity_export_revenue": vs.ElectricityExportRevenue("site", "sell_price", currency="EUR"),
    "grid_import_emissions": vs.GridImportEmissions("site", "carbon"),
}))
```

The microgrid must have `buy_price` and `sell_price` signals in currency/kWh and a
`carbon` signal in kgCO2e/kWh. Convert source units explicitly before supplying them.
Missing signals or nonfinite factor values raise an error. No factor is inferred.
Negative electricity prices are supported.

Import cost and export revenue are separate. Grid-import emissions do not subtract
an export credit. These calculators do not include demand charges, maintenance,
onsite fuel use, or embodied emissions. Record the source and accounting basis of
factors in scenario parameters or the metric's `assumptions`.

To use the same metric name in several microgrids, supply a list:

```python
custom_metrics = {
    "electricity_import_cost": [
        vs.ElectricityImportCost("north", "price"),
        vs.ElectricityImportCost("south", "price"),
    ],
}
```

## Custom metrics

Use `Metric` for calculations that need observations during the simulation.
`start(environment)` runs before stepping; `step(now, states, duration)` receives
an observation and its interval length in seconds. Treat the shared observation as
read-only. `finalize()` returns that calculator's scalar or None. The base metric
initializes `self.value` to zero and returns it on finalization.

```python
class HighImportDuration(vs.Metric):
    def __init__(self):
        super().__init__("h", microgrid="site",
                         description="Hours above 1 kW grid import")

    def step(self, now, states, duration):
        if states["site"]["p_grid"] < -1000:
            self.value += duration / 3600
```

Calculators are independent: `finalize()` receives no other metric results.
Compute constants and derived values in ordinary Python after `env.run()`, then
attach them with `result.add_metric(...)`:

```python
result = recorder.result
result.add_metric("capex", 12000, "EUR", assumptions={"source": "equipment quote"})
result.add_metric("area", 25, "m2", microgrid="site", actor="solar")
site = result.metrics["microgrids"]["site"]
result.add_metric(
    "net_electricity_cost",
    site["electricity_import_cost"] - site["electricity_export_revenue"],
    "EUR", microgrid="site",
    description="Electricity import cost less export revenue",
)
result.save("results/experiment/experiment.json")
```

`add_metric` validates the value, unit, and scope. Names must be unique within a
scope and cannot replace existing metrics. It changes the result in memory; call
`save()` explicitly to persist additions. There is no registration-order dependency
system. Use a `Controller` for control actions.

Annualized estimates, amortized costs, embodied-emissions allocation, and intensities
remain user-defined calculations. Record assumptions such as asset lifetime,
discount rate, representative-period weights, and the denominator in `assumptions`.
Vessim does not automatically extrapolate a short run to a year or label all production
as renewable. Renewable attribution through storage needs a defined tracking model.

See [custom_metrics.py](https://github.com/dos-group/vessim/blob/main/examples/custom_metrics.py)
for a runnable example combining constants, incremental metrics, derived metrics,
and an objective vector for an external optimizer.

## Consuming and comparing results

```python
result = vs.ExperimentResult.load("results/experiment")
if result.execution["status"] == "completed":
    objectives = [
        result.metrics["run"]["capex"],
        result.metrics["microgrids"]["site"]["electricity_import_cost"],
    ]
```

Check status and undefined values before supplying objectives to an optimizer.
Objective directions, weights, normalization, and constraints belong in the caller.
Configuration is descriptive metadata, not a serialized Python model or checkpoint.
User-supplied parameters record study-specific inputs and seeds.

The format identifies itself as `vessim.experiment`, schema version 1. `to_dict()`
returns a detached, validated record. `load(path)` and the viewer use the same
validation for versions, status, scoped numeric values, definitions, and CSV
references. Nonfinite values and inline trajectories are rejected.

`timeseries` is a relative CSV path or null. A loaded result remembers the original
directory; `result.timeseries_path` resolves its CSV independently of the working
directory. Saving in that directory keeps the reference. Saving elsewhere copies
the CSV beside the new JSON as `<JSON stem>.timeseries.csv`; the original result
and files stay where they were. Move the JSON and its CSV together when moving
files manually. In-memory recording and disabled time series both produce null
in the summary.

The [battery sizing study](https://github.com/dos-group/vessim/blob/main/examples/battery_sizing_study.py)
collects these same records under `experiments` in one `vessim.study` JSON file after
all scenarios finish. It does not create a directory per scenario. Python can turn
selected parameters and metrics into a comparison table without loading trajectories.
The [strategy comparison](https://github.com/dos-group/vessim/blob/main/examples/strategy_comparison.py)
writes each experiment once in its own directory; open the parent directory in the
viewer. It does not also duplicate the records in a study file.

The viewer reads the same experiment records, including metrics-only results.
Charts are available when time series were recorded. See the [viewer CLI](../api_reference/cli.md)
for supported inputs. The CSV schema is fixed by the first tick.
New columns later in a run raise an error rather than producing ambiguous rows.
CSV columns use dot-separated state paths. Within each path segment, `%` is escaped
as `%25` and `.` as `%2E`, so an actor named `a.b` remains distinct from nested
state beneath actor `a`. Microgrid identifiers remain strings, even names such as
`123`, `true`, or `NA`.

`Recorder` replaces `Summary`, `MemoryLogger`, and `CsvLogger`. The new JSON format
replaces `metadata.yaml`. Existing YAML experiment folders need to be regenerated
for the current viewer. No legacy writer or automatic format conversion is included.

During development, embedded observation arrays and `ConstantMetric` were removed.
Regenerate recordings with embedded trajectories. Replace constants with
`result.add_metric(...)` after the run, and replace `finalize(metrics)` with
independent `finalize()` calculations or ordinary post-run Python.
