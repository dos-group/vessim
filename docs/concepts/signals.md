# Actors and signals

[`vs.Consumer`](../api_reference/actor.md#vessim.Consumer) represents electrical loads, such as computing equipment or cooling.
[`vs.Producer`](../api_reference/actor.md#vessim.Producer) represents generation, such as solar panels or wind turbines.
Both are subclasses of [`vs.Actor`](../api_reference/actor.md#vessim.Actor), which also supports prosumers that consume and produce power.

Add these components to your microgrid's `actors` list.
Their inputs can be static, follow a recorded trace, or come from live measurements.

## Static signals

Actors with static inputs are the simplest form of actor.
Pass a number to model fixed demand or generation:

```python
import vessim as vs

load = vs.Consumer("load", signal=700)
solar = vs.Producer("solar", signal=1000)
```

A [controller](controllers.md#demand-response) can change demand with `load.signal = 500`, which takes effect at the next actor update.

## Trace signals

Use [`vs.Trace`](../api_reference/signal.md#vessim.Trace) to describe demand or generation over time.
Create a trace from a pandas Series or DataFrame:

```python
import pandas as pd

profile = pd.Series([0, 1000, 0], index=[0, 3600, 7200])
solar = vs.Producer("solar", signal=vs.Trace(profile))
```

<a id="load-a-csv"></a>

You can also load a trace from a CSV file.
For example, save this hourly profile as `input.csv`, with elapsed seconds in the first column:

```csv
seconds,load,solar
0,700,0
3600,700,1200
7200,700,2400
10800,700,1200
14400,700,0
18000,700,0
21600,700,0
```

Select the column for each actor:

```python
inputs = vs.Trace.from_csv("input.csv")
load = vs.Consumer("load", signal=inputs.select("load"))
solar = vs.Producer("solar", signal=inputs.select("solar"))
```

The trace holds each value until the next timestamp.
Use a profile covering your simulation period.
See the [Trace reference](../api_reference/signal.md#vessim.Trace) for calendar timestamps, scaling, and data requirements.

The [CSV example](https://github.com/dos-group/vessim/blob/main/examples/replay_csv.py) runs this profile:

```console
python examples/replay_csv.py input.csv --hours 6
```

## Live signals

Live signals read measurements from a running system.
For example, [`vs.PrometheusSignal`](../api_reference/signal.md#vessim.PrometheusSignal) can supply measured server power from Prometheus.
See [live measurements](live.md#use-live-measurements) for setup and an example.

## Custom signals

To calculate an input yourself, implement [`vs.Signal.at()`](../api_reference/signal.md#vessim.Signal.at) as a function of elapsed simulation time in seconds:

```python
class DemandProfile(vs.Signal):
    def at(self, elapsed):
        return 700 if elapsed < 3600 else 1200

load = vs.Consumer("load", signal=DemandProfile())
```

Signals can also supply electricity prices or carbon intensity to policies, controllers, and metrics.
Add them through the microgrid's `grid_signals`, for example `grid_signals={"price": price_trace}`.
See [costs and emissions](results.md#costs-and-emissions) for a complete use case.

For a component with its own behavior, such as a datacenter with a job queue, implement a [custom actor](../api_reference/actor.md#vessim.Actor.sample).
