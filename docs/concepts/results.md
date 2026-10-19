# Results and metrics

How much electricity did your datacenter import, and when did the battery help?
Record a simulation to inspect its time series and calculate metrics you can compare across runs.

## Recorder

Add a [`vs.Recorder`](../api_reference/recorder.md#vessim.Recorder) to your environment before running it:

```python
recorder = env.add_controller(vs.Recorder("results/experiment"))
env.run(3600)
```

This saves the run's configuration and metrics in `experiment.json`, alongside its time series in `timeseries.csv`.
Give each run its own output directory.
Omit the directory to keep results in memory instead.

After the run, use pandas to explore how your system behaved:

```python
frame = recorder.to_df()
site = frame.xs("site", level="microgrid")
print(site.head())
```

The columns include actor power, battery state of charge, and grid exchange.
You can plot these in a notebook or use the CSV in your own analysis tools.
To explore saved runs in the viewer:

```sh
python -m vessim view results/experiment
```

Try the [example results](../viewer/index.html?study=getting-started#results) and [time-series view](../viewer/index.html?study=getting-started#timeseries), or see [Vessim Viewer](../vessim_viewer.md) to open and share your own recordings.

## ExperimentResult

[`vs.ExperimentResult`](../api_reference/recorder.md#vessim.ExperimentResult) keeps a run's configuration, parameters, and metrics together.
Access it through `recorder.result`, or load a saved run to continue your analysis:

```python
result = vs.ExperimentResult.load("results/experiment")
print(result.metrics["microgrids"]["site"]["grid_import"])
```

You can also attach information calculated outside the simulation, such as an equipment cost, and save it with the result:

```python
result.add_metric("capex", 12000, "EUR")
result.save("results/experiment/experiment.json")
```

## Metrics

The recorder calculates energy consumption, generation, grid imports and exports in Wh, plus peak grid import and export in W.
Read them from `recorder.metrics` or a saved result as shown above.
See the [metric definitions](../api_reference/recorder.md#standard-metrics) for the full list.

For larger studies, `Recorder(timeseries=False)` calculates metrics without storing time series.
[Simulation studies](studies.md) shows how to compare configurations across many runs.

### Costs and emissions

To evaluate electricity costs or emissions, supply the corresponding price and carbon-intensity signals and add metric calculators to your recorder:

```python
env.add_microgrid(
    name="site",
    actors=[vs.Consumer("load", signal=700)],
    dispatchables=[vs.GridConnection()],
    grid_signals={
        "price": 0.30,   # EUR/kWh
        "carbon": 0.25,  # kgCO2e/kWh
    },
)
recorder = env.add_controller(vs.Recorder(custom_metrics={
    "cost": vs.ElectricityImportCost("site", "price", currency="EUR"),
    "emissions": vs.GridImportEmissions("site", "carbon"),
}))
```

These calculations combine imported electricity with your signals, which can also be [traces](signals.md#trace-signals) that vary over time.
After the run, read `cost` and `emissions` alongside the standard metrics for `site`.
[`vs.ElectricityExportRevenue`](../api_reference/recorder.md#vessim.ElectricityExportRevenue) can account for electricity sales using a separate export-price signal.

### Custom metrics

Subclass [`vs.Metric`](../api_reference/recorder.md#vessim.Metric) to calculate something specific to your study.
For example, count the hours when grid import exceeds 1 kW:

```python
class HighImportHours(vs.Metric):
    def __init__(self):
        super().__init__("h", microgrid="site")

    def step(self, now, states, duration):
        imported_power = -states["site"]["p_grid"]
        if imported_power > 1000:
            self.value += duration / 3600
```

Vessim calls `step()` for each recorded interval, with its duration in seconds.
Register the calculation as `custom_metrics={"high_import_hours": HighImportHours()}` on your recorder.
Metrics can describe the whole run, a microgrid, or an individual actor.

The [custom-metrics example](https://github.com/dos-group/vessim/blob/main/examples/custom_metrics.py) combines electricity costs, emissions, and equipment costs into study objectives.
