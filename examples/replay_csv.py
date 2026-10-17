"""Replay your own load and solar measurements from a CSV.

Run: python replay_csv.py input.csv --hours 6
The first column is elapsed seconds. Load and solar are nonnegative watts.
See the getting-started guide for a complete sample CSV.
"""

import argparse
from pathlib import Path

import vessim as vs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--hours", type=float, default=6)
    parser.add_argument("--capacity-wh", type=float, default=1000)
    parser.add_argument("--output", type=Path, default=Path("results/replay_csv"))
    args = parser.parse_args()

    traces = vs.Trace.from_csv(args.input)
    with vs.Environment("2026-01-01", step_size=60) as env:
        env.add_microgrid(
            name="site",
            actors=[
                vs.Consumer("load", power=traces.select("load")),
                vs.Producer("solar", power=traces.select("solar")),
            ],
            dispatchables=[
                vs.SimpleBattery("battery", capacity=args.capacity_wh),
                vs.GridConnection(),
            ],
        )
        recorder = env.add_controller(vs.Recorder(args.output))
        env.run(until=args.hours * 3600)

    metrics = recorder.metrics["microgrids"]["site"]
    print(f"Grid import: {metrics['grid_import'] / 1000:.2f} kWh")
    print(f"Grid export: {metrics['grid_export'] / 1000:.2f} kWh")
    print(f"View results: python -m vessim view {args.output}")


if __name__ == "__main__":
    main()
