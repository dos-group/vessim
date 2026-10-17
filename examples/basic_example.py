"""A six-hour simulation with synthetic inputs. No data downloads required.

Run: python basic_example.py
View: python -m vessim view results/basic_example
Walkthrough: https://vessim.readthedocs.io/en/latest/getting_started/
"""

import pandas as pd
import vessim as vs

# An illustrative hourly solar profile, in W. Values are held until the next sample.
solar = vs.Trace(
    pd.Series(
        [0, 1200, 2400, 1200, 0, 0, 0],
        index=[hour * 3600 for hour in range(7)],
    )
)

env = vs.Environment(sim_start="2026-01-01", step_size=60)
env.add_microgrid(
    name="site",
    actors=[
        vs.Consumer("load", signal=700),
        vs.Producer("solar", signal=solar),
    ],
    dispatchables=[vs.SimpleBattery("battery", capacity=1000), vs.GridConnection()],
)
recorder = env.add_controller(vs.Recorder("results/basic_example"))
run = env.run(until=6 * 3600)

metrics = recorder.metrics["microgrids"]["site"]
print(f"Grid import: {metrics['grid_import'] / 1000:.2f} kWh")
print(f"Grid export: {metrics['grid_export'] / 1000:.2f} kWh")
