"""Build the six-study viewer gallery from Python simulations and sampled replay.

Run: .venv/bin/python viewer/design/build_studies.py --trials 100
The tutorial is regenerated. Other recorded runs are reused. Optuna trials are extended
to the requested total. The draft v2 indexes are prototype-only; experiment files
remain canonical and individually readable by Vessim.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "examples"))
from infrastructure_study import SETUPS, run_scenario as sizing  # noqa: E402
from microgrid_comparison import SETUPS as MULTI_SETUPS, run_scenario as multiple  # noqa: E402
from strategy_comparison import run_scenario as dispatch  # noqa: E402

import vessim as vs  # noqa: E402


def write_index(study_id, title, description, configurations, run_parameters=()):
    """Publish grouping only; all measured evidence remains in experiment files."""
    destination = ROOT / "results/viewer-proposal" / study_id
    destination.mkdir(parents=True, exist_ok=True)
    groups = []
    for identifier, name, paths in configurations:
        group = {
            "configuration_id": identifier,
            "runs": [{"path": os.path.relpath(path, destination)} for path in paths],
        }
        if name:
            group["name"] = name
        groups.append(group)
    document = {
        "format": "vessim.study",
        "schema_version": 2,
        "study_id": study_id,
        "name": title,
        "description": description,
        "configurations": groups,
    }
    if run_parameters:
        document["run_parameters"] = list(run_parameters)
    (destination / "study.json").write_text(json.dumps(document, indent=2) + "\n")


def build_getting_started():
    # Execute the tutorial unchanged in its own directory so existing user
    # results/basic_example recordings are never overwritten.
    output = ROOT / "results/viewer-gallery/getting-started"
    path = output / "results/basic_example/experiment.json"
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [sys.executable, str(ROOT / "examples/basic_example.py")],
        cwd=output,
        check=True,
    )
    write_index(
        "getting-started",
        "Getting started",
        "The getting-started tutorial: three days of a 700 W load, Berlin solar "
        "generation scaled to a 2.4 kW installation, a 1 kWh battery and a grid "
        "connection. Recorded directly from examples/basic_example.py with "
        "five-minute simulation steps using datasets/solar_example.csv.",
        [("basic-example", "Basic example", [path])],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=100)
    parser.add_argument("--monte-carlo-runs", type=int, default=1000)
    parser.add_argument(
        "--monte-carlo-configurations",
        nargs="+",
        default=["trial-00000", "trial-00004", "trial-00007"],
    )
    parser.add_argument(
        "--workers", type=int, default=1, help="Processes for native sampled replay"
    )
    args = parser.parse_args()
    if args.trials < 8:
        parser.error("Use at least eight trials to include the reference configurations")
    if args.monte_carlo_runs < 1:
        parser.error("monte-carlo-runs must be positive")
    if args.workers < 1:
        parser.error("workers must be positive")
    started = time.perf_counter()
    output = ROOT / "results/viewer-gallery"
    build_getting_started()
    # Preserve the existing annual sizing data and its simple objective set.
    annual = ROOT / "results/infrastructure-study"
    groups = []
    for name, sizes in SETUPS.items():
        path = annual / name / "experiment.json"
        if not path.exists():
            sizing(annual, name, *sizes, timeseries=True)
        groups.append((name, name.replace("-", " ").capitalize(), [path]))
    write_index(
        "infrastructure-year",
        "Equipment comparison",
        "Eight equipment configurations, each simulated for one year. "
        "Synthetic demand, weather and emissions coefficients; one shared input realization.",
        groups,
        ["seed"],
    )

    search = output / "optuna-search"
    search.mkdir(parents=True, exist_ok=True)
    import optuna

    database = f"sqlite:///{(search / 'optuna.db').resolve()}"
    existing = 0
    if (search / "optuna.db").exists():
        study = optuna.load_study(study_name="infrastructure-cost-emissions", storage=database)
        existing = len(study.trials)
    if existing < args.trials:
        with (search / "search.log").open("a") as log:
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "examples/infrastructure_study.py"),
                    "--output",
                    str(search),
                    "--trials",
                    str(args.trials - existing),
                    "--financial",
                    "--record-trajectories",
                ],
                check=True,
                stdout=log,
                stderr=log,
            )
    study = optuna.load_study(study_name="infrastructure-cost-emissions", storage=database)
    groups = []
    for trial in study.get_trials(states=(optuna.trial.TrialState.COMPLETE,)):
        path = search / trial.user_attrs["vessim_experiment"]
        record = vs.ExperimentResult.load(path)
        if record.run_id != trial.user_attrs["vessim_run_id"]:
            raise ValueError("Optuna run identity mismatch")
        groups.append((record.run_id, None, [path]))
    write_index(
        "optuna-search",
        "Optuna search",
        "Annual equipment-sizing search: minimize annual cost and grid emissions. "
        "Wind, solar, battery capacity and battery power rating vary. "
        "Synthetic tariffs and equipment costs; upfront investment is reported separately.",
        groups,
        ["seed"],
    )
    print(
        f"Optuna: {len(groups)} completed trials. Dashboard: optuna-dashboard {database}",
        flush=True,
    )
    replay = ROOT / "results/viewer-proposal/optuna-2/study.json"
    if not replay.exists():
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "examples/monte_carlo_replay.py"),
                "--runs",
                str(args.monte_carlo_runs),
                "--workers",
                str(args.workers),
                "--configurations",
                *args.monte_carlo_configurations,
            ],
            check=True,
        )
    replay_index = json.loads(replay.read_text())
    if replay_index["sampling"]["runs_per_configuration"] != args.monte_carlo_runs:
        parser.error(
            "Existing Optuna 2 has a different sample count. Use a fresh output directory"
        )
    if [
        c["configuration_id"] for c in replay_index["configurations"]
    ] != args.monte_carlo_configurations:
        parser.error(
            "Existing Optuna 2 uses different configurations. Regenerate the sampled replay"
        )

    groups = []
    for strategy in ("self_consumption", "peak_shaving", "carbon_aware"):
        paths = []
        for seed in range(41, 46):
            run_id = f"{strategy}-s{seed}"
            path = output / "dispatch-comparison" / run_id / "experiment.json"
            if not path.exists():
                dispatch(path.parent.parent, run_id, 4000, strategy, seed)
            paths.append(path)
        groups.append((strategy, strategy.replace("_", " ").capitalize(), paths))
    write_index(
        "dispatch-comparison",
        "Probabilistic sampling",
        "Three dispatch strategies with the same 4 kWh battery and five shared demand "
        "realizations each. One simulated day per run; synthetic load, prices "
        "and carbon intensity.",
        groups,
        ["seed"],
    )
    groups = []
    for name, sizes in MULTI_SETUPS.items():
        path = output / "multiple-microgrids" / name / "experiment.json"
        if not path.exists():
            multiple(path.parent.parent, name, *sizes)
        groups.append((name, name.replace("-", " ").capitalize(), [path]))
    write_index(
        "multiple-microgrids",
        "Multiple microgrids",
        "Three independent microgrids, three equipment configurations, one week per run. "
        "Distinct synthetic demand and weather per microgrid; no inter-site power transfer. "
        "Run totals and coincident import peak are recorded explicitly.",
        groups,
    )
    elapsed = time.perf_counter() - started
    (output / "gallery.json").write_text(
        json.dumps(
            {
                "elapsed_seconds": elapsed,
                "studies": {
                    "getting-started": 1,
                    "infrastructure-year": 8,
                    "optuna-search": len(study.trials),
                    "optuna-2": len(replay_index["configurations"]) * args.monte_carlo_runs,
                    "dispatch-comparison": 15,
                    "multiple-microgrids": 3,
                },
            },
            indent=2,
        )
        + "\n"
    )
    print(
        f"Gallery ready in {elapsed:.1f}s: 1 tutorial, 8 annual, {len(study.trials)} search, "
        f"{len(replay_index['configurations']) * args.monte_carlo_runs} sampled replay, "
        "15 dispatch, 3 multi runs."
    )


if __name__ == "__main__":
    main()
