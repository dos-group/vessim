"""Record actual simulations for the interactive viewer prototype.

Run from the repository root: .venv/bin/python viewer/design/generate_recorded.py
Uses the existing example scenario; input traces and cost assumptions are synthetic.
The grouping manifest is still a proposed study v2, not a production CLI input.
"""

import json
from pathlib import Path
import shutil
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "examples"))
from strategy_comparison import run_scenario  # noqa: E402


def main():
    destination = ROOT / "results/viewer-proposal/recorded"
    configurations = []
    for strategy in ("self_consumption", "peak_shaving", "carbon_aware"):
        for capacity in (1000, 4000, 8000):
            key = f"{strategy}-{capacity}"
            config = {
                "configuration_id": key,
                "name": f"{strategy.replace('_', ' ').capitalize()} / {capacity / 1000:g} kWh",
                "parameters": {"strategy": strategy, "battery_capacity_wh": capacity},
                "conditions": {"input_model": "strategy_comparison.py", "duration_s": 86400},
                "runs": [],
            }
            for seed in (41, 42, 43):
                run_id = f"{key}-s{seed}"
                result = run_scenario(destination / "runs", run_id, capacity, strategy, seed)
                frame = pd.read_csv(destination / "runs" / run_id / "timeseries.csv")
                # An arbitrary user-defined objective, persisted like any other metric.
                result.add_metric(
                    "ramp_limit_exceedances",
                    int((frame.p_grid.diff().abs() > 400).sum()),
                    "1",
                    description="Number of sampled grid-power changes exceeding 400 W",
                    assumptions={"threshold_w": 400, "sample_interval_s": 300},
                )
                result.save(destination / "runs" / run_id / "experiment.json")
                config["runs"].append(
                    {
                        "run_id": run_id,
                        "path": f"runs/{run_id}/experiment.json",
                        "realization": {"id": f"demand-{seed}", "seeds": {"demand": seed}},
                    }
                )
            configurations.append(config)
    (destination / "study.json").write_text(
        json.dumps(
            {
                "format": "vessim.study",
                "schema_version": 2,
                "study_id": "recorded",
                "name": "Dispatch comparison",
                "description": (
                    "Three strategies × three battery sizes × three demand seeds. "
                    "Recorded Vessim simulations with synthetic one-day inputs."
                ),
                "configurations": configurations,
            },
            indent=2,
        )
        + "\n"
    )

    # Make the previously evaluated Optuna results available without running a new search.
    candidates = []
    target = ROOT / "results/viewer-proposal/optuna-recorded"
    for source in sorted((ROOT / "results/optuna-study").glob("trial-*/experiment.json")):
        record = json.loads(source.read_text())
        key = record["run_id"]
        shutil.copytree(source.parent, target / "runs" / key, dirs_exist_ok=True)
        candidates.append(
            {
                "configuration_id": key,
                "name": key,
                "parameters": {k: v for k, v in record["parameters"].items() if k != "seed"},
                "conditions": {"duration_s": record["execution"].get("until")},
                "provenance": {"optuna": {"trial_number": int(key.split("-")[-1])}},
                "runs": [
                    {
                        "run_id": key,
                        "path": f"runs/{key}/experiment.json",
                        "realization": {"id": f"demand-{record['parameters'].get('seed', 42)}"},
                    }
                ],
            }
        )
    if candidates:
        (target / "study.json").write_text(
            json.dumps(
                {
                    "format": "vessim.study",
                    "schema_version": 2,
                    "study_id": "optuna-recorded",
                    "name": "Optuna search",
                    "description": (
                        "Previously recorded optimization trials; synthetic scenario inputs."
                    ),
                    "configurations": candidates,
                },
                indent=2,
            )
            + "\n"
        )
    print(f"Recorded 27 runs; imported {len(candidates)} existing Optuna trials.")


if __name__ == "__main__":
    main()
