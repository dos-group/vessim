"""Replay your own load and solar measurements from a CSV.

Run: python replay_csv.py input.csv --hours 6
The first column is elapsed seconds. Load and solar are nonnegative watts.
See the signals guide for a complete sample CSV.
"""

import argparse
from pathlib import Path

from _common import fresh_output

import vessim as vs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "datasets/replay_example.csv",
    )
    parser.add_argument("--hours", type=float, default=6)
    parser.add_argument("--capacity-wh", type=float, default=1000)
    parser.add_argument("--output", type=Path, default=Path("results/replay_csv"))
    args = parser.parse_args()

    if args.hours <= 0 or args.capacity_wh <= 0:
        parser.error("hours and capacity must be positive")
    traces = vs.Trace.from_csv(args.input)
    fresh_output(args.output)
    with vs.Environment("2026-01-01", step_size=60) as env:
        env.add_microgrid(
            name="site",
            actors=[
                vs.Consumer("load", signal=traces.select("load")),
                vs.Producer("solar", signal=traces.select("solar")),
            ],
            dispatchables=[
                vs.SimpleBattery("battery", capacity=args.capacity_wh),
                vs.GridConnection(),
            ],
        )
        recorder = env.add_controller(vs.Recorder(args.output, run_id="csv-replay"))
        env.run(until=args.hours * 3600)

    metrics = recorder.metrics["microgrids"]["site"]
    print(f"Grid import: {metrics['grid_import'] / 1000:.2f} kWh")
    print(f"Grid export: {metrics['grid_export'] / 1000:.2f} kWh")
    print(f"View results: python -m vessim view {args.output}")


if __name__ == "__main__":
    main()
