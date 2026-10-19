"""Compare battery capacities against the same seeded demand scenarios.

python examples/battery_sizing_study.py --scenarios 10 --workers 4
python -m vessim view results/battery-sizing
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
from pathlib import Path

import numpy as np
import pandas as pd
import vessim as vs
from _common import fresh_output, write_study

CAPACITIES = (1000, 2000, 4000)
SOLAR: vs.Trace


def initialize_worker():
    global SOLAR
    seconds = np.arange(0, 86400, 300)
    watts = 5000 * np.maximum(0, np.sin((seconds / 3600 - 6) * np.pi / 12))
    SOLAR = vs.Trace(pd.Series(watts, index=seconds))


def run_scenario(task):
    capacity, seed, output, timeseries = task
    rng = np.random.default_rng(seed)
    seconds = np.arange(0, 86400, 300)
    load = vs.Trace(pd.Series(rng.uniform(500, 1500, len(seconds)), index=seconds))
    run_id = f"battery-{capacity}-s{seed}"
    with vs.Environment("2026-01-01", step_size=300) as env:
        env.add_microgrid(
            name="site",
            actors=[vs.Producer("solar", SOLAR), vs.Consumer("load", load)],
            dispatchables=[
                vs.SimpleBattery("battery", capacity, initial_soc=0.5),
                vs.GridConnection(),
            ],
        )
        recorder = env.add_controller(
            vs.Recorder(
                output / run_id,
                timeseries=timeseries,
                run_id=run_id,
                parameters={"capacity_wh": capacity, "seed": seed},
            )
        )
        env.run(24 * 3600)
    result = recorder.result
    result.add_metric(
        "battery_capex", capacity / 1000 * 400, "EUR", assumptions={"battery_eur_per_kwh": 400}
    )
    result.save(output / run_id / "experiment.json")
    return run_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenarios", type=int, default=5)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=Path("results/battery-sizing"))
    parser.add_argument("--no-timeseries", action="store_true")
    args = parser.parse_args()
    if args.scenarios <= 0 or args.workers <= 0 or args.seed < 0:
        parser.error("scenarios and workers must be positive, seed must be nonnegative")
    fresh_output(args.output)
    seeds = range(args.seed, args.seed + args.scenarios)
    tasks = [
        (capacity, seed, args.output, not args.no_timeseries)
        for capacity in CAPACITIES
        for seed in seeds
    ]
    if args.workers == 1:
        initialize_worker()
        list(map(run_scenario, tasks))
    else:
        with ProcessPoolExecutor(
            max_workers=args.workers,
            initializer=initialize_worker,
            mp_context=multiprocessing.get_context("spawn"),
        ) as pool:
            list(pool.map(run_scenario, tasks))
    write_study(
        args.output,
        "battery-sizing",
        "Battery sizing",
        [
            (
                f"battery-{capacity}",
                f"{capacity / 1000:g} kWh",
                [f"battery-{capacity}-s{seed}" for seed in seeds],
            )
            for capacity in CAPACITIES
        ],
        run_parameters=["seed"],
        description=(
            "Three battery capacities supply the same demand scenarios "
            "alongside solar generation. "
            "Compare how additional storage changes grid imports and how consistent those savings "
            "are across different daily demand profiles."
        ),
    )
    print(f"Saved {len(tasks)} runs. View: python -m vessim view {args.output}")


if __name__ == "__main__":
    main()
