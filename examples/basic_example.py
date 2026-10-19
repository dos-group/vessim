"""Three days of constant demand and Berlin solar generation from a bundled CSV.

Run: python examples/basic_example.py
View: python -m vessim view results/basic_example
Walkthrough: https://vessim.readthedocs.io/en/latest/getting_started/
"""

import argparse
from pathlib import Path

from _common import fresh_output, write_study

import vessim as vs


def run(output):
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
    recorder = env.add_controller(vs.Recorder(output, run_id="basic-example"))
    env.run(until=3 * 24 * 3600)

    metrics = recorder.metrics["microgrids"]["site"]
    print(f"Grid import: {metrics['grid_import'] / 1000:.2f} kWh")
    print(f"Grid export: {metrics['grid_export'] / 1000:.2f} kWh")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("results/basic_example"))
    args = parser.parse_args()
    run(fresh_output(args.output))
    write_study(
        args.output,
        "getting-started",
        "Getting started",
        [("basic-example", "Basic example", ["."])],
        description=(
            "A small microgrid supplies steady demand with solar power, a battery, "
            "and a grid connection. "
            "Three days of solar data show the battery charging during sunny periods and "
            "supplying demand when generation falls. "
            "Open the time series to follow how power flows through the system."
        ),
    )


if __name__ == "__main__":
    main()
