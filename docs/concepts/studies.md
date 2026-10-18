# Simulation studies

How much battery storage does your datacenter need, and does that change with its workload?
Simulation studies let you compare infrastructure and control strategies across demand, weather, and operating scenarios.
You might test a few designs against thousands of possible conditions, or explore a wide range of configurations.

Use `vs.Environment` to run each scenario as fast as computation allows, then compare its [recorded metrics](results.md).

## Compare battery sizes

A battery that works well for one workload may be too small for another.
This example tests three capacities against four synthetic demand profiles, producing twelve runs.
Each capacity faces the same demand profiles and solar trace, so differences in grid imports reflect the storage choice.

```python
import numpy as np
import pandas as pd
import vessim as vs

seconds = [hour * 3600 for hour in range(7)]
solar = vs.Trace(pd.Series([0, 1200, 2400, 1200, 0, 0, 0], index=seconds))
rows = []

for seed in range(4):
    rng = np.random.default_rng(seed)
    load = vs.Trace(pd.Series(rng.uniform(500, 900, len(seconds)), index=seconds))
    for capacity in (1000, 2000, 3000):
        run_id = f"battery-{capacity}-seed-{seed}"
        with vs.Environment("2026-01-01", step_size=1800) as env:
            env.add_microgrid(
                name="site",
                actors=[vs.Consumer("load", signal=load), vs.Producer("solar", signal=solar)],
                dispatchables=[vs.SimpleBattery("battery", capacity), vs.GridConnection()],
            )
            recorder = env.add_controller(vs.Recorder(
                f"results/study/{run_id}",
                timeseries=False,
                run_id=run_id,
                parameters={"capacity_wh": capacity, "seed": seed},
            ))
            env.run(6 * 3600)
        rows.append({
            "capacity_wh": capacity,
            "seed": seed,
            "grid_import_wh": recorder.metrics["microgrids"]["site"]["grid_import"],
        })

print(pd.DataFrame(rows).groupby("capacity_wh")["grid_import_wh"].agg(["mean", "max"]))
```

## Compare the results

The table shows average and maximum grid imports for each capacity across the four demand scenarios.
Here, increasing capacity from 1 to 2 kWh reduces imports, but 3 kWh provides no further reduction over these six-hour scenarios.

Open the saved runs together to explore the comparison:

```console
python -m vessim view results/study
```

Each run records its battery capacity and scenario seed, so you can identify the conditions behind a result.
To investigate when a battery filled or ran out, enable time series by removing `timeseries=False` from the recorder.

Explore the larger [equipment comparison](../viewer/index.html?study=infrastructure-year#results), [probabilistic dispatch study](../viewer/index.html?study=dispatch-comparison#results), or [multiple-microgrid study](../viewer/index.html?study=multiple-microgrids#results) in the viewer.

## Extend the study

Replace the synthetic demand with your own workload traces, add weather years, or compare dispatch policies.
For probabilistic studies, sample uncertain inputs and look at the distribution of outcomes, such as the fraction of scenarios that meet your import target.
Reuse the same scenarios and starting conditions across designs to make the comparison meaningful.

Independent runs can execute in parallel.
The [battery-sizing example](https://github.com/dos-group/vessim/blob/main/examples/battery_sizing_study.py) shows how to distribute scenarios across worker processes.
The [infrastructure example](https://github.com/dos-group/vessim/blob/main/examples/infrastructure_study.py) compares wind, solar, and storage over a full year.

When the design space is too large to enumerate, use [optimization](optimization.md) to search for promising configurations.
