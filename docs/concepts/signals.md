# Signals and Datasets

A **Signal** provides a time-varying value to the simulation: the power consumed by a server, the power produced by a solar panel, the carbon intensity of the public grid. Every `Actor` and every entry in a microgrid's `grid_signals` is backed by a `Signal`.

Vessim ships three signal types and lets you write your own.

## StaticSignal

`StaticSignal` always returns the same value. Useful for baseline loads, fixed production, or as a placeholder during testing:

```python
import vessim as vs

signal = vs.StaticSignal(value=42)
```

A `StaticSignal` can be updated at runtime via `set_value()`, which lets a [Controller](controllers.md) flip a load on and off or step it through a schedule.

## Trace

`Trace` replays a time series. Vessim aligns the data with simulation time even when its native resolution differs from the simulation step size.

### Included datasets

Vessim ships with several ready-to-use datasets that can be loaded with `vs.Trace.load()`.

**Solcast (solar irradiance)** — provided by [Solcast](https://solcast.com/):

- `solcast2022_global` — 2022 solar production for several global cities. Normalized (0–1); pass `params={"scale": ...}` to scale to your peak power.
- `solcast2022_germany` — 2022 solar data for representative locations in Germany (North, South, East, West).

```python
solar = vs.Trace.load(
    dataset="solcast2022_global",
    column="Berlin",
    params={"scale": 5000},  # 5 kW peak
)
```

**WattTime (carbon intensity)** — provided by [WattTime](https://watttime.org/):

- `watttime2023_caiso-north` — Marginal Operating Emissions Rate (MOER) for Northern California, 2023.

```python
carbon = vs.Trace.load("watttime2023_caiso-north")
```

### Custom data

To replay your own data, pass a pandas `Series` or `DataFrame` directly:

```python
import pandas as pd
import vessim as vs

data = pd.Series(
    [100, 200, 150, 100],
    index=pd.date_range("2022-01-01", periods=4, freq="5min"),
)

custom = vs.Trace(data)
```

## SiL Signals

For real-time simulations, **Software-in-the-Loop (SiL)** signals poll data from external sources in the background:

- `PrometheusSignal` — pull live metrics (e.g. server power) from a Prometheus server.
- `WatttimeSignal` — fetch live grid carbon intensity from the WattTime API.

You can also subclass `SilSignal` to wrap any other live data source. See [Software-in-the-Loop](sil.md) for the full picture.
