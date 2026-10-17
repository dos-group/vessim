"""Compare wind, solar, and battery sizes over a configurable simulation horizon.

python examples/infrastructure_study.py --record-trajectories
python examples/infrastructure_study.py --trials 24 --output results/infrastructure-search
python -m vessim view results/infrastructure-study

Inspired by dos-group/vessim-opt, not a reproduction of its models or results.
All traces and embodied-emissions coefficients are illustrative synthetic inputs.
Optuna is optional; without --trials this evaluates eight named configurations.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import time

import numpy as np
import pandas as pd

import vessim as vs

MODEL_VERSION = 1
START = "2026-01-01"
# kgCO2e/kW for generation; kgCO2e/kWh for storage. Demonstration coefficients,
# not measured equipment inventories, annualized emissions, or lifecycle factors.
EMBODIED = {"wind_kw": 400, "solar_kw": 600, "battery_kwh": 100}
SETUPS = {
    "grid-only": (0, 0, 0),
    "solar": (0, 3000, 0),
    "wind": (3000, 0, 0),
    "mixed": (1500, 2000, 0),
    "mixed-storage": (1500, 2000, 4000),
    "wind-storage": (3000, 0, 4000),
    "solar-storage": (0, 5000, 8000),
    "high-renewables": (3000, 4000, 8000),
}


def inputs(days: int = 365, step_seconds: int = 3600, seed: int = 42) -> pd.DataFrame:
    """Generate shared synthetic load, capacity factors, and grid carbon intensity.

    Weather is generated hourly before sampling, so changing step size retains
    the same underlying realization. Finer steps hold hourly inputs constant.
    This is a demonstration time series, not a calibrated weather/demand model.
    """
    if days <= 0 or step_seconds <= 0 or 3600 % step_seconds or seed < 0:
        raise ValueError("days must be positive, step_seconds must divide 3600, seed >= 0")
    hours = np.arange(days * 24)
    day, hour = hours / 24, hours % 24
    season = np.cos(2 * np.pi * (day - 172) / 365)
    cloud_rng, wind_rng, load_rng = [
        np.random.default_rng(s) for s in np.random.SeedSequence(seed).spawn(3)
    ]
    cloud = np.repeat(cloud_rng.uniform(0.25, 1, days), 24)
    daylight = 12 + 4 * season
    solar = np.maximum(0, np.sin(np.pi * (hour - (12 - daylight / 2)) / daylight))
    solar *= (0.75 + 0.2 * season) * cloud
    # Persistent wind variation; generate warm-up values before the first sample.
    noise = wind_rng.normal(size=len(hours) + 48)
    smooth = np.convolve(noise, np.ones(24) / np.sqrt(24), mode="valid")[: len(hours)]
    wind = np.clip(0.38 - 0.10 * season + 0.20 * smooth, 0, 0.95)
    load = 1000 + 100 * np.sin(2 * np.pi * (hour - 8) / 24)
    load += 70 * season + load_rng.uniform(-70, 70, len(hours))
    carbon = np.clip(0.40 - 0.20 * wind - 0.12 * solar, 0.08, 0.55)
    hourly = pd.DataFrame(
        {"load_kw": load, "solar_cf": solar, "wind_cf": wind, "carbon": carbon},
        index=hours * 3600,
    )
    return hourly.reindex(np.arange(0, days * 86400, step_seconds), method="ffill")


def run_scenario(
    output: Path,
    run_id: str,
    wind_kw: float,
    solar_kw: float,
    battery_kwh: float,
    *,
    days: int = 365,
    step_seconds: int = 3600,
    seed: int = 42,
    timeseries: bool = False,
) -> vs.ExperimentResult:
    """Record one configuration with a common input realization and explicit assumptions."""
    sizes = {"wind_kw": wind_kw, "solar_kw": solar_kw, "battery_kwh": battery_kwh}
    if any(not math.isfinite(value) or value < 0 for value in sizes.values()):
        raise ValueError("Equipment sizes must be finite and nonnegative")
    if (output / run_id).exists():
        raise FileExistsError(f"Preserving existing run: {output / run_id}")
    frame = inputs(days, step_seconds, seed)

    def trace(values):
        return vs.Trace(values)

    dispatchables = []
    if battery_kwh:
        dispatchables.append(
            vs.SimpleBattery("battery", battery_kwh * 1000, initial_soc=0, c_rate=0.5)
        )
    dispatchables.append(vs.GridConnection())
    emissions = vs.GridImportEmissions("site", "carbon")
    emissions.assumptions.update(
        {
            "source": "synthetic hourly carbon intensity; not a regional forecast",
            "input_model_version": MODEL_VERSION,
            "export_credit": False,
            "battery": "lossless, 0.5C, starts empty; no credit for terminal stored energy",
        }
    )
    with vs.Environment(START, step_size=step_seconds, name="Infrastructure sizing") as env:
        env.add_microgrid(
            [
                vs.Producer("wind", signal=trace(frame.wind_cf * wind_kw * 1000)),
                vs.Producer("solar", signal=trace(frame.solar_cf * solar_kw * 1000)),
                vs.Consumer("datacenter", signal=trace(frame.load_kw * 1000)),
            ],
            dispatchables=dispatchables,
            name="site",
            grid_signals={"carbon": trace(frame.carbon)},
        )
        recorder = env.add_controller(
            vs.Recorder(
                output / run_id,
                run_id=run_id,
                timeseries=timeseries,
                parameters={
                    **sizes,
                    "days": days,
                    "step_seconds": step_seconds,
                    "seed": seed,
                    "input_model_version": MODEL_VERSION,
                },
                custom_metrics={"grid_emissions": emissions},
            )
        )
        env.run(days * 86400)
    result = recorder.result
    result.add_metric(
        "initial_embodied_emissions",
        sum(sizes[key] * factor for key, factor in EMBODIED.items()),
        "kgCO2e",
        description="Illustrative upfront emissions of installed wind, solar, and storage",
        assumptions={
            "source": "synthetic demonstration coefficients; not a lifecycle assessment",
            "wind_kgco2e_per_kw": EMBODIED["wind_kw"],
            "solar_kgco2e_per_kw": EMBODIED["solar_kw"],
            "battery_kgco2e_per_kwh": EMBODIED["battery_kwh"],
            "excludes": "existing datacenter, grid infrastructure, replacements, end of life",
            "annualized": False,
        },
    )
    result.save(output / run_id / "experiment.json")
    return result


def objective_values(result: vs.ExperimentResult) -> tuple[float, float]:
    """Return recorded objectives, rejecting unsuccessful or undefined evidence."""
    if result.execution["status"] != "completed":
        raise ValueError(f"Run {result.run_id} did not complete")
    values = (
        result.metrics["run"]["initial_embodied_emissions"],
        result.metrics["microgrids"]["site"]["grid_emissions"],
    )
    if any(value is None or not math.isfinite(value) for value in values):
        raise ValueError("Objectives must be finite recorded metrics")
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("results/infrastructure-study"))
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--step-seconds", type=int, default=3600)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--trials", type=int, default=0, help="Optuna trials; 0 = eight fixed setups"
    )
    parser.add_argument("--record-trajectories", action="store_true")
    args = parser.parse_args()
    if args.trials < 0:
        parser.error("trials must be nonnegative")
    try:
        inputs(args.days, args.step_seconds, args.seed)
    except ValueError as exc:
        parser.error(str(exc))
    settings = {
        "model_version": MODEL_VERSION,
        "days": args.days,
        "step_seconds": args.step_seconds,
        "seed": args.seed,
        "timeseries": args.record_trajectories,
    }
    # Resuming an optimization must not silently mix different evaluation conditions.
    contract = {
        **settings,
        "mode": "optuna" if args.trials else "fixed",
        "embodied": EMBODIED,
        "sampler": {"name": "NSGAII", "population_size": 8} if args.trials else None,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    contract_path = args.output / "scenario.json"
    if contract_path.exists() and json.loads(contract_path.read_text()) != contract:
        parser.error("Evaluation settings changed; choose a fresh --output directory")
    contract_path.write_text(json.dumps(contract, indent=2) + "\n")
    scenario_args = {k: v for k, v in settings.items() if k != "model_version"}
    started = time.perf_counter()
    if args.trials:
        try:
            import optuna
        except ImportError as exc:
            raise SystemExit(
                "Install optional tooling: pip install optuna optuna-dashboard"
            ) from exc
        storage = f"sqlite:///{(args.output / 'optuna.db').resolve()}"
        study = optuna.create_study(
            study_name="infrastructure-emissions",
            storage=storage,
            load_if_exists=True,
            directions=["minimize", "minimize"],
            sampler=optuna.samplers.NSGAIISampler(seed=args.seed, population_size=8),
        )
        study.set_metric_names(
            ["Upfront equipment emissions (kgCO2e)", "Grid-import emissions (kgCO2e)"]
        )
        if not study.trials:
            # Include interpretable reference setups alongside the search candidates.
            for wind, solar, battery in SETUPS.values():
                study.enqueue_trial({"wind_kw": wind, "solar_kw": solar, "battery_kwh": battery})

        def objective(trial):
            sizes = {
                "wind_kw": trial.suggest_int("wind_kw", 0, 5000, step=500),
                "solar_kw": trial.suggest_int("solar_kw", 0, 6000, step=500),
                "battery_kwh": trial.suggest_int("battery_kwh", 0, 12000, step=1000),
            }
            run_id = f"trial-{trial.number:05d}"
            trial.set_user_attr("vessim_run_id", run_id)
            trial.set_user_attr("vessim_experiment", f"{run_id}/experiment.json")
            result = run_scenario(args.output, run_id, **sizes, **scenario_args)
            return objective_values(result)

        study.optimize(objective, n_trials=args.trials)
        print(f"Pareto trial numbers: {[trial.number for trial in study.best_trials]}")
        print(f"Optuna Dashboard: optuna-dashboard {storage}")
    else:
        for name, (wind, solar, battery) in SETUPS.items():
            result = run_scenario(args.output, name, wind, solar, battery, **scenario_args)
            upfront, operational = objective_values(result)
            print(f"{name}: upfront {upfront:,.0f}; operating {operational:,.0f} kgCO2e")
    print(f"Elapsed: {time.perf_counter() - started:.2f}s")
    print(f"View recorded results: python -m vessim view {args.output}")


if __name__ == "__main__":
    main()
