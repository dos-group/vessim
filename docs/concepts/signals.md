# Signals and Datasets

A **Signal** provides a time-varying value to the simulation: the power consumed by a server, the power produced by a solar panel, the carbon intensity of the public grid. Every `Actor` and every entry in a microgrid's `grid_signals` is backed by a `Signal`.

Vessim ships three signal types: `StaticSignal` for constant values, `Trace` for replaying historical data, and `SilSignal` for live data sources. 
You can easily write your own, only take care that `signal.at(elapsed)` returns the value at the elapsed time the simulation has accumulated since `sim_start`.

## StaticSignal

`StaticSignal` always returns the same value. It is useful for baseline loads, fixed production, or as a placeholder during testing:

```python
import vessim as vs

signal = vs.StaticSignal(value=42)
```

You can update a `StaticSignal` at runtime via `set_value()`. This allows a [Controller](controllers.md) to toggle loads or follow a schedule.

## Trace

`Trace` replays a time series row-by-row. Its index is an **offset** in seconds since the trace's start (row 0 at `0`); as the simulation advances, `Trace` returns the value at the matching offset.

### From in-memory data

`Trace` accepts a pandas `Series` or `DataFrame` with either a numeric index (interpreted as seconds) or a `TimedeltaIndex`:

```python
import pandas as pd
import vessim as vs

trace = vs.Trace(pd.Series([50, 200, 50], index=[0, 3600, 7200]))

trace = vs.Trace(pd.Series(
    [50, 200, 50],
    index=pd.to_timedelta(["0s", "1h", "2h"]),
))
```

Sampling does not need to be uniform. The index must start at 0 — to delay a trace, pad the beginning of your data with zeros or NaNs.

### Loading from a CSV

`Trace.from_csv` reads a CSV whose first column is the offset in seconds and remaining columns hold values:

```text
time,trace_a,trace_b
0,0.10,0.35
3600,0.22,0.47
7200,0.38,0.41
```

```python
load = vs.Trace.from_csv(
    "datasets/load_example.csv",
    column="trace_a",  # required if the CSV has multiple value columns
)
```

`scale=` multiplies all values (handy for normalized data), and missing cells (per column) are dropped.

### Datetime data and `anchor`

Calendar-stamped data is also supported. Pass an `anchor` to mark which row should sit at offset=0; earlier rows are dropped. This works both for in-memory data and for CSVs with a datetime first column:

```text
datetime,Berlin,Stockholm,Mumbai
2022-06-08 00:05:00,0.0,0.0,0.0
2022-06-08 00:10:00,0.0,0.0,0.0
2022-06-08 00:15:00,0.0,0.0,0.0
```

```python
solar = vs.Trace.from_csv(
    "datasets/solcast.csv",
    anchor="2022-06-09 00:00:00",
    column="Berlin",
    scale=5000,
)
```

## Public data sources

Vessim's CSV schema is intentionally minimal so you can produce it from any source. Common providers for simulation data include:

- Carbon intensity: [Electricity Maps](https://www.electricitymaps.com/) or [WattTime](https://watttime.org/).
- Weather and solar: [Open-Meteo](https://open-meteo.com/) (free historical archive), [Solcast](https://solcast.com/) (commercial irradiance and PV forecasts), or [NREL NSRDB](https://nsrdb.nrel.gov/) (high-resolution US data). For an example for a public live station feed, see [HTW Berlin](https://wetter.htw-berlin.de/).
- Electricity prices: [ENTSO-E Transparency Platform](https://transparency.entsoe.eu/) (European day-ahead and balancing markets), [EIA Open Data](https://www.eia.gov/opendata/) (US wholesale and retail), [Nord Pool](https://www.nordpoolgroup.com/) (Nordic and Baltic spot markets), or [Electricity Maps](https://www.electricitymaps.com/) (price data alongside carbon intensity).

For real-time data instead of historical traces, see the **Software-in-the-Loop signals** below.

## Software-in-the-Loop signals

For real-time simulations, **Software-in-the-Loop (SiL)** signals poll data from external sources in the background:

- `PrometheusSignal`: pull live metrics (e.g. server power) from a Prometheus server.
- `WatttimeSignal`: fetch live grid carbon intensity from the WattTime API.

SiL signals are time-independent: they ignore the `elapsed` argument and always return their most recent cached value. Use them with `Environment.live(...)` rather than `Environment(...)`. See [Software-in-the-Loop](sil.md).

You can subclass `SilSignal` to wrap any other live data source.
