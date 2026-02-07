# Signals and Datasets

Vessim uses **Signals** to represent time-varying data like renewable energy production or carbon intensity. This tutorial explains the different types of signals available and how to use them.

## Static Signal

The `StaticSignal` always returns a constant value. It is useful for representing baseline loads or for testing scenarios with fixed power production.

```python
import vessim as vs

# A signal that always returns 42
signal = vs.StaticSignal(value=42)
```

A `StaticSignal` can be updated during a simulation. This allows [Controllers](3_controller.md) to dynamically adjust the behavior of actors or other components.

## Trace (Historical Data)

A `Trace` allows you to replay historical time-series data. Vessim automatically handles the alignment of this data with the simulation time, even if the resolution of your data differs from the simulation step size.

### Included Datasets
Vessim comes with several ready-to-use datasets for solar irradiance and grid carbon intensity which can be loaded using `vs.Trace.load()`.

#### Solcast (Solar Irradiance)
Vessim includes solar irradiance data provided by [Solcast](https://solcast.com/).

**Global Dataset (`solcast2022_global`)**
Contains 2022 solar production data for major global cities. The data is normalized (0-1), so you should scale it to your desired peak power.

```python
solar_signal = vs.Trace.load(
    dataset="solcast2022_global", 
    column="Berlin", 
    params={"scale": 5000} # Scales the normalized data to 5000W peak
)
```
<iframe src="../../assets/solcast2022_global_plot.html" width="100%" height="500px"></iframe>

**Germany Dataset (`solcast2022_germany`)**
Contains 2022 solar data for representative locations in Germany (North, South, East, West).
<iframe src="../../assets/solcast2022_germany_plot.html" width="100%" height="500px"></iframe>

#### WattTime (Carbon Intensity)
Vessim includes grid carbon intensity data provided by [WattTime](https://watttime.org/).

**CAISO North (`watttime2023_caiso-north`)**
Contains the Marginal Operating Emissions Rate (MOER) for Northern California for 2023.
<iframe src="../../assets/watttime2023_caiso-north_plot.html" width="100%" height="500px"></iframe>

### Custom Datasets
You can also use your own time-series data by loading it into a pandas DataFrame or Series.

```python
import pandas as pd

# Create a custom time-series
data = pd.Series(
    [100, 200, 150, 100], 
    index=pd.date_range("2022-01-01", periods=4, freq="5min")
)

# Create a Trace
custom_signal = vs.Trace(data)
```

## Software-in-the-Loop Signals

For simulations that interact with the real world, Vessim provides **Software-in-the-Loop (SiL)** signals. These signals poll data from external sources in real-time while the simulation is running.

*   **PrometheusSignal**: Pulls live metrics (like power usage) from a Prometheus server.
*   **WatttimeSignal**: Fetches live grid carbon intensity from the WattTime API.

To learn more about how to use these signals and how they integrate into real-time simulations, check out the [Software-in-the-Loop tutorial](4_sil.md).
