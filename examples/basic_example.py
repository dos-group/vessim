"""Three days of constant demand and Berlin solar generation from a bundled CSV.

Run: python basic_example.py
View: python -m vessim view results/basic_example
Walkthrough: https://vessim.readthedocs.io/en/latest/getting_started/
"""

from pathlib import Path

import vessim as vs

# Scale the normalized solar profile to a 2.4 kW installation.
solar = vs.Trace.from_csv(
    Path(__file__).resolve().parents[1] / "datasets/solar_example.csv",
    column="Berlin",
    scale=2400,
)

env = vs.Environment(sim_start="2026-01-01", step_size=5 * 60)
env.add_microgrid(
    name="site",
    actors=[
        vs.Consumer("load", signal=700),
        vs.Producer("solar", signal=solar),
    ],
    dispatchables=[vs.SimpleBattery("battery", capacity=1000), vs.GridConnection()],
)
recorder = env.add_controller(vs.Recorder("results/basic_example"))
run = env.run(until=3 * 24 * 3600)

metrics = recorder.metrics["microgrids"]["site"]
print(f"Grid import: {metrics['grid_import'] / 1000:.2f} kWh")
print(f"Grid export: {metrics['grid_export'] / 1000:.2f} kWh")
