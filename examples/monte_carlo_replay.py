"""Re-evaluate the existing Optuna configurations under shared sampled years.

python examples/monte_carlo_replay.py --runs 1000 --workers 8

Every sample runs a fresh native Vessim Environment. Worker processes evaluate
small groups of seeded runs, while the parent streams compact viewer files.
The existing configurations are replayed without launching another optimization.
"""

from __future__ import annotations

import argparse
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import json
import math
import multiprocessing
import re
from pathlib import Path
import time

import numpy as np

from infrastructure_study import CAPEX, EMBODIED, LIFETIMES, inputs
import vessim as vs

ROOT = Path(__file__).resolve().parents[1]
MODEL_VERSION = 2
# Independent triangular annual factors, specified as minimum, mode, maximum.
FACTORS = {
    "demand_multiplier": (0.75, 1.0, 1.30),
    "solar_multiplier": (0.80, 1.0, 1.20),
    "wind_multiplier": (0.75, 1.0, 1.25),
    "price_multiplier": (0.65, 1.0, 1.50),
}


def sampled_inputs(seed: int, days: int = 365):
    frame = inputs(days=days, seed=seed)
    rng = np.random.default_rng([seed, MODEL_VERSION])
    factors = {name: float(rng.triangular(*bounds)) for name, bounds in FACTORS.items()}
    frame.load_kw *= factors["demand_multiplier"]
    frame.solar_cf = (frame.solar_cf * factors["solar_multiplier"]).clip(0, 1)
    frame.wind_cf = (frame.wind_cf * factors["wind_multiplier"]).clip(0, 1)
    frame.carbon = np.clip(0.40 - 0.20 * frame.wind_cf - 0.12 * frame.solar_cf, 0.08, 0.55)
    hours = (frame.index.to_numpy() / 3600) % 24
    frame["price"] = np.where((hours >= 17) & (hours < 21), 0.30, 0.15)
    frame.price *= factors["price_multiplier"]
    frame["export_price"] = 0.04 * factors["price_multiplier"]
    return frame, factors


def run_scenario(configuration_id, parameters, seed, days=365):
    """Run one sampled scenario through native dispatch and metric recording."""
    frame, factors = sampled_inputs(seed, days)
    sizes = {key: parameters[key] for key in CAPEX}
    battery = (
        vs.SimpleBattery(
            "battery", sizes["battery_kwh"] * 1000, c_rate=parameters["battery_c_rate"]
        )
        if sizes["battery_kwh"]
        else None
    )
    assumptions = {
        "source": "illustrative synthetic annual scenarios, not calibrated forecasts",
        "annual_factors": FACTORS,
        "sampling": "independent annual factors, same seeds across configurations",
        "input_model_version": MODEL_VERSION,
        "battery": "lossless, starts empty, C-rate limited, no terminal energy credit",
        "installed_costs": CAPEX,
        "lifetimes_years": LIFETIMES,
        "allocation": "straight-line annual capital allocation",
    }
    metrics = {
        "grid_emissions": vs.GridImportEmissions("Microgrid 1", "carbon"),
        "electricity_cost": vs.ElectricityImportCost("Microgrid 1", "price"),
        "export_revenue": vs.ElectricityExportRevenue("Microgrid 1", "export_price"),
    }
    for metric in metrics.values():
        metric.assumptions.update(assumptions)
    with vs.Environment("2026-01-01", step_size=3600, backend="native") as env:
        env.add_microgrid(
            name="Microgrid 1",
            actors=[
                vs.Producer("wind", vs.Trace(frame.wind_cf * sizes["wind_kw"] * 1000)),
                vs.Producer("solar", vs.Trace(frame.solar_cf * sizes["solar_kw"] * 1000)),
                vs.Consumer("datacenter", vs.Trace(frame.load_kw * 1000)),
            ],
            dispatchables=([battery] if battery is not None else []) + [vs.GridConnection()],
            grid_signals={
                key: vs.Trace(frame[key]) for key in ("carbon", "price", "export_price")
            },
        )
        recorder = env.add_controller(
            vs.Recorder(
                timeseries=False,
                run_id=f"{configuration_id}-s{seed}",
                parameters={
                    **sizes,
                    "battery_c_rate": parameters["battery_c_rate"],
                    "days": days,
                    "step_seconds": 3600,
                    "input_model_version": MODEL_VERSION,
                    "seed": seed,
                    **factors,
                },
                custom_metrics=metrics,
            )
        )
        env.run(days * 86400)
    result = recorder.result
    result.add_metric(
        "final_battery_energy",
        battery.charge_level if battery is not None else 0,
        "Wh",
        microgrid="Microgrid 1",
        description="Stored energy after the final dispatch interval",
    )
    capital = sum(sizes[key] * CAPEX[key] for key in sizes)
    annual_capital = sum(sizes[key] * CAPEX[key] / LIFETIMES[key] for key in sizes)
    grid = result.metrics["microgrids"]["Microgrid 1"]
    result.add_metric(
        "initial_embodied_emissions",
        sum(sizes[key] * EMBODIED[key] for key in sizes),
        "kgCO2e",
        assumptions={**assumptions, "embodied_coefficients": EMBODIED},
    )
    result.add_metric("equipment_capex", capital, "EUR", assumptions=assumptions)
    result.add_metric("annualized_equipment_cost", annual_capital, "EUR", assumptions=assumptions)
    if days == 365:
        result.add_metric(
            "annual_cost",
            annual_capital + grid["electricity_cost"] - grid["export_revenue"],
            "EUR",
            assumptions=assumptions,
        )
    return result.to_dict()


def evaluate_chunk(task):
    """Return compact evidence for a small group of independent native runs."""
    identity, parameters, seeds = task
    started = time.perf_counter()
    records = []
    shared = None
    for seed in seeds:
        try:
            record = run_scenario(identity, parameters, seed)
        except Exception as exc:
            raise RuntimeError(f"Simulation {identity}-s{seed} failed") from exc
        if shared is None:
            shared = {
                key: value for key, value in record.items() if key not in ("run_id", "metrics")
            }
            shared["parameters"] = {
                key: value
                for key, value in record["parameters"].items()
                if key not in ("seed", *FACTORS)
            }
            shared["execution"] = {"status": "completed"}
        records.append(
            {
                "run_id": record["run_id"],
                "parameters": {key: record["parameters"][key] for key in ("seed", *FACTORS)},
                "execution": record["execution"],
                "metrics": record["metrics"],
            }
        )
    return identity, shared, records, time.perf_counter() - started


def evaluate_tasks(tasks, workers):
    """Keep at most two chunks per worker in flight and yield in input order."""
    if workers == 1:
        yield from map(evaluate_chunk, tasks)
        return
    tasks = iter(tasks)
    pool = ProcessPoolExecutor(
        max_workers=workers, mp_context=multiprocessing.get_context("spawn")
    )
    pending = deque()
    try:
        for _ in range(workers * 2):
            task = next(tasks, None)
            if task is None:
                break
            pending.append(pool.submit(evaluate_chunk, task))
        while pending:
            result = pending.popleft().result()
            task = next(tasks, None)
            if task is not None:
                pending.append(pool.submit(evaluate_chunk, task))
            yield result
    finally:
        for future in pending:
            future.cancel()
        pool.shutdown(wait=True, cancel_futures=True)


def load_configurations(source_index, configuration_ids=None):
    index = json.loads(source_index.read_text())
    configs = []
    seen = set()
    for group in index["configurations"]:
        identity = group["configuration_id"]
        if not isinstance(identity, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.-]*", identity
        ):
            raise ValueError("Configuration IDs must be safe filenames")
        if identity in seen:
            raise ValueError("Duplicate source configuration IDs")
        seen.add(identity)
        source = json.loads((source_index.parent / group["runs"][0]["path"]).read_text())
        config = {key: source["parameters"][key] for key in (*CAPEX, "battery_c_rate")}
        for key, value in config.items():
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
            ):
                raise ValueError(f"Invalid {key} for configuration {identity}")
        if config["battery_c_rate"] == 0:
            raise ValueError("Battery C-rate must be positive")
        configs.append((identity, config))
    if not configs:
        raise ValueError("Source study has no configurations")
    if configuration_ids is not None:
        if not configuration_ids or len(set(configuration_ids)) != len(configuration_ids):
            raise ValueError("Select at least one configuration without duplicate IDs")
        by_id = dict(configs)
        missing = set(configuration_ids) - by_id.keys()
        if missing:
            raise ValueError(f"Unknown configuration IDs: {sorted(missing)}")
        configs = [(identity, by_id[identity]) for identity in configuration_ids]
    return configs


def build(
    source_index: Path,
    output: Path,
    runs: int,
    seed_start=10000,
    chunk_size=4,
    workers=1,
    configuration_ids=None,
):
    """Stream a seeded native sweep to a new directory using a persistent pool."""
    for name, value, minimum in (
        ("runs", runs, 1),
        ("chunk_size", chunk_size, 1),
        ("workers", workers, 1),
        ("seed_start", seed_start, 0),
    ):
        if type(value) is not int or value < minimum:
            raise ValueError(f"{name} must be an integer >= {minimum}")
    configs = load_configurations(source_index, configuration_ids)
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    tasks = (
        (identity, config, range(seed_start + begin, seed_start + min(begin + chunk_size, runs)))
        for identity, config in configs
        for begin in range(0, runs, chunk_size)
    )
    counts = dict.fromkeys((identity for identity, _ in configs), 0)
    completed = 0
    worker_seconds = simulation_seconds = writing_seconds = 0.0
    last_progress = started
    results = evaluate_tasks(tasks, workers)
    try:
        for identity, shared, records, elapsed in results:
            worker_seconds += elapsed
            simulation_seconds += sum(record["execution"]["wall_time"] for record in records)
            writing_started = time.perf_counter()
            partial = output / f"{identity}.json.partial"
            first = counts[identity] == 0
            with partial.open("x" if first else "a") as stream:
                if first:
                    header = json.dumps(
                        {
                            "format": "vessim.viewer.run-batch",
                            "schema_version": 1,
                            "shared": shared,
                        },
                        separators=(",", ":"),
                        allow_nan=False,
                    )
                    stream.write(header[:-1] + ',"runs":[')
                for record in records:
                    if counts[identity]:
                        stream.write(",")
                    stream.write(json.dumps(record, separators=(",", ":"), allow_nan=False))
                    counts[identity] += 1
                if counts[identity] == runs:
                    stream.write("]}")
            if counts[identity] == runs:
                partial.rename(output / f"{identity}.json")
            writing_seconds += time.perf_counter() - writing_started
            completed += len(records)
            now = time.perf_counter()
            if now - last_progress >= 1 or completed == len(configs) * runs:
                print(
                    f"Completed {completed:,}/{len(configs) * runs:,} native runs "
                    f"in {now - started:.1f}s",
                    flush=True,
                )
                last_progress = now
    finally:
        results.close()
    document = {
        "format": "vessim.study",
        "schema_version": 2,
        "study_id": "optuna-2",
        "name": "Optuna 2",
        "description": f"The {len(configs)} existing Optuna configurations, each evaluated over "
        f"{runs:,} shared synthetic years with native Vessim. Annual demand, solar, wind "
        "and price factors vary alongside hourly weather and demand. This re-evaluates "
        "the original configurations without optimizing them again.",
        "run_parameters": ["seed", *FACTORS],
        "configurations": [
            {
                "configuration_id": identity,
                "name": identity.replace("trial-", "Trial "),
                "run_batch": f"{identity}.json",
            }
            for identity, _ in configs
        ],
        "sampling": {
            "runs_per_configuration": runs,
            "seed_start": seed_start,
            "annual_factors": FACTORS,
            "model_version": MODEL_VERSION,
        },
        "runtime": {
            "evaluator": "native",
            "workers": workers,
            "chunk_size": chunk_size,
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "wall_seconds": time.perf_counter() - started,
            "worker_wall_seconds_sum": worker_seconds,
            "simulation_wall_seconds_sum": simulation_seconds,
            "writing_seconds": writing_seconds,
            "evaluations": completed,
            "timing_scope": "Pool startup, inputs, native simulations and summary output",
        },
    }
    temporary = output / "study.json.partial"
    temporary.write_text(json.dumps(document, indent=2, allow_nan=False) + "\n")
    temporary.rename(output / "study.json")
    return document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=1000)
    parser.add_argument("--seed-start", type=int, default=10000)
    parser.add_argument("--chunk-size", type=int, default=4)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--configurations", nargs="+", help="Saved configuration IDs to replay")
    parser.add_argument(
        "--source", type=Path, default=ROOT / "results/viewer-proposal/optuna-search/study.json"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "results/viewer-proposal/optuna-2")
    args = parser.parse_args()
    try:
        build(
            args.source,
            args.output,
            args.runs,
            args.seed_start,
            args.chunk_size,
            args.workers,
            args.configurations,
        )
    except (ValueError, FileExistsError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
