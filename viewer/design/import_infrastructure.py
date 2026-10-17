"""Expose canonical infrastructure results in the prototype's draft study manifest.

python viewer/design/import_infrastructure.py

Run examples/infrastructure_study.py first (fixed setups and/or Optuna).
This adapter belongs to the prototype, not the experiment format or scenario API.
It references the original experiment files and their original trajectory origins.
"""

import json
import os
from pathlib import Path

from vessim import ExperimentResult

ROOT = Path(__file__).resolve().parents[2]


def import_study(source: Path, study_id: str, title: str):
    destination = ROOT / "results/viewer-proposal" / study_id
    records = sorted(source.glob("*/experiment.json"))
    if not records:
        print(f"Skipping {source}: no experiments")
        return
    configurations = {}
    for path in records:
        record = ExperimentResult.load(path)
        parameters = {k: v for k, v in record.parameters.items() if k != "seed"}
        key = json.dumps(parameters, sort_keys=True)
        if key not in configurations:
            sizes = record.parameters
            configurations[key] = {
                "configuration_id": f"setup-{len(configurations):03d}",
                "name": (
                    f"Wind {sizes['wind_kw']:g} kW · Solar {sizes['solar_kw']:g} kW · "
                    f"Battery {sizes['battery_kwh']:g} kWh"
                ),
                "parameters": parameters,
                "conditions": {
                    "duration_s": record.execution["simulated_duration"],
                    "start": "2026-01-01",
                    "inputs": "Synthetic seasonal load, wind, solar, and carbon intensity",
                },
                "runs": [],
            }
        configurations[key]["runs"].append(
            {
                "run_id": record.run_id,
                "path": os.path.relpath(path, destination),
                "realization": {
                    "id": f"synthetic-{record.parameters['seed']}",
                    "seeds": {"inputs": record.parameters["seed"]},
                },
            }
        )
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "study.json").write_text(
        json.dumps(
            {
                "format": "vessim.study",
                "schema_version": 2,
                "study_id": study_id,
                "name": title,
                "description": (
                    "Wind, solar, and battery sizing for a ~1 MW datacenter. "
                    "Synthetic inputs and illustrative emissions coefficients. "
                    "Lossless 0.5C battery, starts empty; unrestricted grid connection."
                ),
                "configurations": list(configurations.values()),
            },
            indent=2,
        )
        + "\n"
    )
    print(f"{study_id}: {len(configurations)} configurations, {len(records)} runs")


if __name__ == "__main__":
    import_study(ROOT / "results/infrastructure-study", "infrastructure-year", "Annual sizing")
    import_study(ROOT / "results/infrastructure-search", "infrastructure-search", "Annual search")
