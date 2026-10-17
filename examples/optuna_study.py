"""Use Optuna for a cost/emissions trade-off; Vessim records every simulation.

Install optional tools: pip install optuna optuna-dashboard
python examples/optuna_study.py --trials 20
optuna-dashboard sqlite:///results/optuna-study/optuna.db
python -m vessim view results/optuna-study

The two objectives are illustrative battery CAPEX and one-day grid emissions;
no lifetime cost or lifecycle-emissions model is implied. Optuna owns search
state; Vessim stores experiment evidence. This example runs trials sequentially.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from urllib.parse import quote

from strategy_comparison import run_scenario


def objective_values(result):
    """Reject unsuccessful or undefined results before reporting objectives."""
    if result.execution["status"] != "completed":
        raise ValueError(f"Experiment {result.run_id} did not complete")
    values = (
        result.metrics["run"]["battery_capex"],
        result.metrics["microgrids"]["campus"]["grid_emissions"],
    )
    if any(value is None or not math.isfinite(value) for value in values):
        raise ValueError("Objectives must be finite recorded metrics")
    return values


def main():
    try:
        import optuna
    except ImportError as exc:
        raise SystemExit(
            "Install optional tools with: pip install optuna optuna-dashboard"
        ) from exc
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=20, help="Additional trials this invocation")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=Path("results/optuna-study"))
    parser.add_argument("--record-trajectories", action="store_true")
    parser.add_argument("--viewer-url", default="http://localhost:8710")
    args = parser.parse_args()
    if args.trials <= 0 or args.seed < 0:
        parser.error("trials must be positive; seed must be nonnegative")
    args.output.mkdir(parents=True, exist_ok=True)
    storage = f"sqlite:///{(args.output / 'optuna.db').resolve()}"
    study = optuna.create_study(
        study_name="battery-cost-emissions",
        storage=storage,
        load_if_exists=True,
        directions=["minimize", "minimize"],
        sampler=optuna.samplers.NSGAIISampler(seed=args.seed),
    )

    def objective(trial):
        capacity = trial.suggest_float("battery_capacity_wh", 500, 10000, step=500)
        strategy = trial.suggest_categorical(
            "strategy", ["self_consumption", "peak_shaving", "carbon_aware"]
        )
        run_id = f"trial-{trial.number:05d}"
        trial.set_user_attr("vessim_run_id", run_id)
        trial.set_user_attr("vessim_experiment", f"{run_id}/experiment.json")
        trial.set_user_attr("vessim_viewer", f"{args.viewer_url.rstrip('/')}/#run={quote(run_id)}")
        result = run_scenario(
            args.output,
            run_id,
            capacity,
            strategy,
            seed=args.seed,
            timeseries=args.record_trajectories,
        )
        return objective_values(result)

    study.optimize(objective, n_trials=args.trials)
    print(f"Pareto trial numbers: {[trial.number for trial in study.best_trials]}")
    print(f"Optuna Dashboard: optuna-dashboard {storage}")
    print(f"Vessim detail: python -m vessim view {args.output}")


if __name__ == "__main__":
    main()
