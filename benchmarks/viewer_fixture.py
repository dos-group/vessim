"""Generate deterministic synthetic summary records for viewer performance checks.

python -m benchmarks.viewer_fixture --runs 10000 --output results/viewer-benchmark.json
These records are UI fixtures, not simulation outcomes or scientific evidence.
"""

import argparse
import json
from pathlib import Path
import random


def generate(count):
    rng = random.Random(42)
    for index in range(count):
        capacity = rng.uniform(1000, 10000)
        strategy = ("self_consumption", "peak_shaving", "carbon_aware")[index % 3]
        yield {
            "format": "vessim.experiment",
            "schema_version": 1,
            "run_id": f"scenario-{index:05d}",
            "parameters": {"strategy": strategy, "capacity_wh": capacity, "seed": index % 20},
            "config": {
                "environment": {"sim_start": "2026-01-01", "step_size": 300},
                "microgrids": {
                    "campus": {"actors": [], "dispatchables": [], "policy": {"type": strategy}}
                },
            },
            "execution": {
                "status": "failed" if index % 97 == 0 else "completed",
                "simulated_duration": 86400,
                "wall_time": 0.3,
            },
            "metrics": {
                "run": {"capex": capacity * 0.4, "undefined": None},
                "microgrids": {
                    "campus": {
                        "grid_import": max(0, 12000 - capacity * 0.6 + rng.gauss(0, 800)),
                        "emissions": rng.uniform(1, 8),
                    }
                },
                "actors": {},
            },
            "metric_definitions": {
                "run": {
                    "capex": {"unit": "EUR", "assumptions": {"synthetic": True}},
                    "undefined": {"unit": "1"},
                },
                "microgrids": {
                    "campus": {"grid_import": {"unit": "Wh"}, "emissions": {"unit": "kgCO2e"}}
                },
                "actors": {},
            },
            "timeseries": None,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=10000)
    parser.add_argument("--output", type=Path, default=Path("results/viewer-benchmark.json"))
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("runs must be positive")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {
                "format": "vessim.study",
                "schema_version": 1,
                "experiments": list(generate(args.runs)),
            }
        )
    )
    print(f"{args.runs} synthetic records; {args.output.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
