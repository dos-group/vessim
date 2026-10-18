# Recording and metrics

See [Results and metrics](../concepts/results.md) for recording choices and custom calculations, or [Simulation studies](../concepts/studies.md) for comparing runs.

::: vessim.Recorder
::: vessim.ExperimentResult
::: vessim.Metric
::: vessim.ElectricityImportCost
::: vessim.ElectricityExportRevenue
::: vessim.GridImportEmissions

## Standard metrics

| Scope | Metrics | Unit |
| --- | --- | --- |
| Actor and microgrid | `energy_produced`, `energy_consumed` | Wh |
| Microgrid | `grid_import`, `grid_export` | Wh |
| Microgrid | `peak_grid_import`, `peak_grid_export` | W |

Actor production and consumption are accumulated separately from sampled power.
Microgrid production and consumption sum the actors, excluding dispatchables and external simulator inputs.
Grid import and export integrate the net exchange of all grid connections.
Peak values are sampled maxima, not rolling billing demand.

Energy totals cover the full [simulation duration](environment.md#time-and-final-state), including a shortened final interval.
For incomplete runs, check `execution["status"]` and the [partial-recording semantics](#partial-recordings).

## Saved records

An experiment uses `format="vessim.experiment"` and `schema_version=1`.
Use `ExperimentResult.load()` and `save()` to read and write validated records.
`to_dict()` provides a detached dictionary for other tools.

`timeseries` is a relative CSV path or null.
`timeseries_path` resolves it from the original record location.
Saving a loaded record elsewhere copies the CSV beside the new JSON.
Saving in-memory observations does not persist a trajectory unless the recorder was configured with an output directory.

Keep JSON and CSV together when moving recordings.
For embedded `vessim.study` records, CSV paths are relative to the study file.
Prefer opening a collection of experiment directories in the viewer when each run has its own CSV.

CSV columns are fixed by the first observation.
Nested state fields use dot-separated paths, escaping literal `.` as `%2E` and `%` as `%25` within names.
Changing the state schema during a run raises an error.

## Partial recordings

`Recorder` accumulates metrics for an interval when its starting observation is recorded.
The interval is clipped to the requested simulation horizon.
If a run fails or is interrupted, the last accumulated interval can extend beyond the point execution reached, particularly in live mode.
Check `execution["status"]` before using such totals in a comparison.
