"""Compare battery sizes under varying loads using independent simulation runs.

python examples/battery_sizing_study.py --scenarios 1000 --workers 4 --output results/study.json
Each scenario gets fresh mutable models and a deterministic seed. Only compact
metrics are returned to the parent process. It writes one file after the study.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import multiprocessing
from pathlib import Path

import numpy as np
import pandas as pd
import vessim as vs

SOLAR: vs.Trace


def initialize_worker():
    global SOLAR
    # Synthetic one-day profile, shared by all scenarios in this worker.
    seconds = np.arange(0, 86401, 300)
    watts = 5000 * np.maximum(0, np.sin((seconds / 3600 - 6) * np.pi / 12))
    SOLAR = vs.Trace(pd.Series(watts, index=seconds))


def run_scenario(scenario):
    index, seed = scenario
    rng = np.random.default_rng(np.random.SeedSequence([seed, index]))
    config = {
        "capacity_wh": float(rng.uniform(1000, 5000)),
        "load_w": float(rng.uniform(500, 1500)),
    }
    with vs.Environment("2026-01-01", step_size=300) as env:
        env.add_microgrid(
            name="site",
            actors=[
                vs.Producer("solar", signal=SOLAR),
                vs.Consumer("load", signal=config["load_w"]),
            ],
            dispatchables=[
                vs.SimpleBattery("battery", config["capacity_wh"], initial_soc=0.5),
                vs.GridConnection(),
            ],
        )
        recorder = env.add_controller(
            vs.Recorder(
                timeseries=False,
                run_id=str(index),
                parameters={"seed": seed, **config},
            )
        )
        env.run(24 * 3600)
    result = recorder.result
    # Illustrative assumptions, replace with your equipment data.
    result.add_metric(
        "battery_capex",
        config["capacity_wh"] / 1000 * 400,
        "EUR",
        assumptions={"battery_eur_per_kwh": 400},
    )
    return result.to_dict()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenarios", type=int, default=10)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=Path("results/study.json"))
    args = parser.parse_args()
    if args.scenarios <= 0 or args.workers <= 0 or args.seed < 0:
        parser.error("scenarios/workers must be positive. Seed must be nonnegative")
    scenarios = [(index, args.seed) for index in range(args.scenarios)]
    if args.workers == 1:
        initialize_worker()
        results = list(map(run_scenario, scenarios))
    else:
        with ProcessPoolExecutor(
            max_workers=args.workers,
            initializer=initialize_worker,
            mp_context=multiprocessing.get_context("spawn"),
        ) as pool:
            results = list(
                pool.map(
                    run_scenario, scenarios, chunksize=max(1, args.scenarios // (args.workers * 4))
                )
            )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    configurations = []
    for result in results:
        relative = Path(args.output.stem + "-runs") / result["run_id"] / "experiment.json"
        destination = args.output.parent / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(result, indent=2) + "\n")
        configurations.append(
            {"configuration_id": result["run_id"], "runs": [{"path": relative.as_posix()}]}
        )
    args.output.write_text(
        json.dumps(
            {
                "format": "vessim.study",
                "schema_version": 2,
                "study_id": args.output.stem,
                "name": "Battery sizing",
                "run_parameters": ["seed"],
                "configurations": configurations,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"Saved {len(results)} scenarios to {args.output}")


if __name__ == "__main__":
    main()
