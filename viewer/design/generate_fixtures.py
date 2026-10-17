"""Generate illustrative records for the study/configuration/run design proposal.

Run from the repository root: .venv/bin/python viewer/design/generate_fixtures.py
These are synthetic UI fixtures, not simulation or optimization results. The draft
study v2 manifests are for reviewing the proposal, not current CLI inputs.
"""

from pathlib import Path
import json

from vessim.recorder import ExperimentResult


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "results/viewer-proposal"


def write_study(study_id, name, candidates, repeats):
    directory = OUTPUT / study_id
    configurations = []
    for index, (strategy, capacity) in enumerate(candidates):
        configuration_id = f"c{index + 1:02d}"
        parameters = {"strategy": strategy, "battery_capacity_wh": capacity}
        configuration = {
            "configuration_id": configuration_id,
            "name": f"{strategy.replace('_', ' ').capitalize()} / {capacity / 1000:g} kWh",
            "parameters": parameters,
            "conditions": {
                "input_model": "illustrative-demand-v1",
                "sim_start": "2026-01-01T00:00:00Z",
                "duration_s": 86400,
                "grid_limit_w": 10000,
            },
            "runs": [],
        }
        if study_id == "optimization":
            configuration["provenance"] = {
                "optuna": {"study_name": "illustrative-search", "trial_number": index}
            }
        for repeat in range(repeats):
            run_id = f"{configuration_id}-r{repeat + 1:02d}"
            status = "completed"
            if study_id == "fixed" and index == 2 and repeat == 3:
                status = "failed"
            if study_id == "fixed" and index == 4 and repeat == 3:
                status = "interrupted"
            # Deliberately simple fixture values; no simulation is being run.
            value = round(13000 - capacity * 0.6 - index % 2 * 500 + (repeat - 1.5) * 600)
            if status != "completed":
                value = round(value / 3)
            if study_id == "fixed" and index == 5 and repeat == 2:
                value = None
            run_path = directory / "runs" / run_id / "experiment.json"
            result = ExperimentResult(
                run_id=run_id,
                config={
                    "environment": {
                        "sim_start": configuration["conditions"]["sim_start"],
                        "step_size": 300,
                    },
                    "microgrids": {"campus": {"fixture": True}},
                },
                parameters={**parameters, "demand_seed": 100 + repeat},
                execution={
                    "status": status,
                    "simulated_duration": 86400 if status == "completed" else 28800,
                    "until": 86400,
                    "steps": 288 if status == "completed" else 96,
                },
                metrics={
                    "run": {"battery_capex": capacity * 0.4},
                    "microgrids": {"campus": {"grid_import": value}},
                    "actors": {},
                },
                metric_definitions={
                    "run": {
                        "battery_capex": {
                            "unit": "EUR",
                            "description": "Illustrative battery capital cost",
                            "assumptions": {"eur_per_kwh": 400, "fixture": True},
                        }
                    },
                    "microgrids": {
                        "campus": {
                            "grid_import": {
                                "unit": "Wh",
                                "description": "Illustrative imported grid energy",
                                "assumptions": {"fixture": True, "requested_duration_s": 86400},
                            }
                        }
                    },
                    "actors": {},
                },
                timeseries=None,
            )
            result.save(run_path)
            # Prove that existing standalone run loading is unaffected.
            assert ExperimentResult.load(run_path).to_dict() == result.to_dict()
            configuration["runs"].append(
                {
                    "run_id": run_id,
                    "path": str(run_path.relative_to(directory)),
                    "realization": {
                        "id": f"demand-{repeat + 1:02d}",
                        "seeds": {"demand": 100 + repeat},
                    },
                }
            )
        configurations.append(configuration)
    study = {
        "format": "vessim.study",
        "schema_version": 2,
        "study_id": study_id,
        "name": name,
        "description": "Synthetic design fixture; not measured or simulated evidence.",
        "configurations": configurations,
    }
    (directory / "study.json").write_text(json.dumps(study, indent=2) + "\n")


def main():
    write_study(
        "fixed",
        "Dispatch comparison",
        [
            (strategy, capacity)
            for capacity in (1000, 4000, 8000)
            for strategy in ("self_consumption", "peak_shaving")
        ],
        repeats=4,
    )
    write_study(
        "optimization",
        "Infrastructure search",
        [
            ("self_consumption" if i % 2 else "peak_shaving", capacity)
            for i, capacity in enumerate((1000, 2500, 4000, 5500, 8000, 3000, 6500, 4500))
        ],
        repeats=1,
    )
    print(f"Wrote draft study manifests and 32 canonical v1 run records to {OUTPUT}")


if __name__ == "__main__":
    main()
