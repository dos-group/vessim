"""Benchmark native Vessim using the sampled annual infrastructure scenario.

Run with .venv/bin/python benchmarks/native_study.py.
Writes raw timings and profiles under results/benchmark-native.
No simulation models or engine methods are replaced.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import cProfile
import io
import json
import multiprocessing
import os
from pathlib import Path
import platform
import pstats
import statistics
import sys
import tempfile
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))

import vessim as vs  # noqa: E402
from monte_carlo_replay import sampled_inputs  # noqa: E402


CONFIGS = [
    dict(wind_kw=0, solar_kw=0, battery_kwh=0, battery_c_rate=0.5),
    dict(wind_kw=1500, solar_kw=2000, battery_kwh=4000, battery_c_rate=0.25),
    dict(wind_kw=5000, solar_kw=6000, battery_kwh=12000, battery_c_rate=1.0),
]


class Observer(vs.Controller):
    """Request normal detached state observations without recording metrics."""

    def step(self, now, microgrid_states):
        pass


def run_one(config, seed, mode="summary", step_seconds=3600, output=None):
    started = time.perf_counter()
    frame, _ = sampled_inputs(seed)
    if step_seconds != 3600:
        frame = frame.reindex(np.arange(0, 365 * 86400, step_seconds), method="ffill")
    input_done = time.perf_counter()
    battery = (
        vs.SimpleBattery("battery", config["battery_kwh"] * 1000, c_rate=config["battery_c_rate"])
        if config["battery_kwh"]
        else None
    )
    with vs.Environment("2026-01-01", step_size=step_seconds, backend="native") as env:
        env.add_microgrid(
            name="site",
            actors=[
                vs.Producer("wind", vs.Trace(frame.wind_cf * config["wind_kw"] * 1000)),
                vs.Producer("solar", vs.Trace(frame.solar_cf * config["solar_kw"] * 1000)),
                vs.Consumer("datacenter", vs.Trace(frame.load_kw * 1000)),
            ],
            dispatchables=([battery] if battery is not None else []) + [vs.GridConnection()],
            grid_signals={
                key: vs.Trace(frame[key]) for key in ("carbon", "price", "export_price")
            },
        )
        recorder = None
        if mode == "observer":
            env.add_controller(Observer())
        elif mode != "none":
            custom = (
                {
                    "grid_emissions": vs.GridImportEmissions("site", "carbon"),
                    "electricity_cost": vs.ElectricityImportCost("site", "price"),
                    "export_revenue": vs.ElectricityExportRevenue("site", "export_price"),
                }
                if mode != "physical"
                else {}
            )
            recorder = env.add_controller(
                vs.Recorder(
                    output,
                    timeseries=mode in ("trajectory_memory", "trajectory_csv"),
                    custom_metrics=custom,
                    parameters={**config, "seed": seed},
                )
            )
        setup_done = time.perf_counter()
        result = env.run(365 * 86400)
        run_done = time.perf_counter()
    assert result.steps == 365 * 86400 // step_seconds
    checksum = recorder.metrics["microgrids"]["site"] if recorder is not None else None
    return {
        "config": config,
        "seed": seed,
        "mode": mode,
        "step_seconds": step_seconds,
        "input_seconds": input_done - started,
        "setup_seconds": setup_done - input_done,
        "run_seconds": run_done - setup_done,
        "total_seconds": time.perf_counter() - started,
        "steps": result.steps,
        "metrics": checksum,
    }


def worker(task):
    config, seed, output = task
    return run_one(config, seed, output=output)


def summary(rows):
    return {
        name: {
            "median": statistics.median(row[name] for row in rows),
            "min": min(row[name] for row in rows),
            "max": max(row[name] for row in rows),
        }
        for name in ("input_seconds", "setup_seconds", "run_seconds", "total_seconds")
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results/benchmark-native")
    parser.add_argument("--repeats", type=int, default=6)
    parser.add_argument("--jobs", type=int, default=100)
    parser.add_argument("--workers", nargs="+", type=int, default=[1, 2, 4, 8])
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    report = {
        "system": {
            "python": sys.version,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "logical_cpus": os.cpu_count(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "scope": "365 days, three actors, battery where configured, grid, six traces",
        "ablations": {},
        "parallel": [],
    }

    def save():
        (args.output / "timings.json").write_text(json.dumps(report, indent=2) + "\n")

    # Warm imports and allocation paths before collecting unprofiled timings.
    run_one(CONFIGS[1], 9999)
    with tempfile.TemporaryDirectory(prefix="native-benchmark-", dir=args.output) as scratch:
        modes = [
            "none",
            "observer",
            "physical",
            "summary",
            "summary_disk",
            "trajectory_memory",
            "trajectory_csv",
        ]
        rows = {mode: [] for mode in modes}
        # Rotate execution order so later modes do not always get a warmer CPU.
        for repeat in range(args.repeats):
            order = modes[repeat % len(modes) :] + modes[: repeat % len(modes)]
            for mode in order:
                output = (
                    Path(scratch) / f"{mode}-{repeat}"
                    if mode in ("summary_disk", "trajectory_csv")
                    else None
                )
                rows[mode].append(
                    run_one(CONFIGS[repeat % 3], 10000 + repeat, mode, output=output)
                )
            print(f"Ablations {repeat + 1}/{args.repeats}", flush=True)
        for mode in modes:
            report["ablations"][mode] = {"summary": summary(rows[mode]), "runs": rows[mode]}
            print(mode, json.dumps(summary(rows[mode])), flush=True)
        save()

        fine = [run_one(CONFIGS[1], 10000 + i, step_seconds=300) for i in range(3)]
        report["five_minute"] = {"summary": summary(fine), "runs": fine}
        save()
        print("Five-minute", json.dumps(summary(fine)), flush=True)

        for mode in ("none", "summary", "trajectory_csv"):
            profiler = cProfile.Profile()
            for i in range(3):
                profiler.runcall(
                    run_one,
                    CONFIGS[1],
                    10000 + i,
                    mode,
                    output=(
                        Path(scratch) / f"profile-{mode}-{i}" if mode == "trajectory_csv" else None
                    ),
                )
            profiler.dump_stats(str(args.output / f"{mode}.prof"))
            stream = io.StringIO()
            stats = pstats.Stats(profiler, stream=stream)
            stats.strip_dirs().sort_stats("cumulative").print_stats(50)
            stats.sort_stats("tottime").print_stats(40)
            (args.output / f"{mode}-profile.txt").write_text(stream.getvalue())
            print(f"Profiled {mode}", flush=True)

        source = ROOT / "results/viewer-proposal/optuna-search/study.json"
        if source.exists():
            configs = []
            for config in json.loads(source.read_text())["configurations"]:
                record = json.loads((source.parent / config["runs"][0]["path"]).read_text())
                configs.append({key: record["parameters"][key] for key in CONFIGS[0]})
        else:
            configs = CONFIGS
        report["parallel_configuration_source"] = (
            str(source) if source.exists() else "three references"
        )
        reference = None
        for workers in args.workers:
            tasks = [
                (configs[i % len(configs)], 10000 + i, Path(scratch) / f"parallel-{workers}-{i}")
                for i in range(args.jobs)
            ]
            started = time.perf_counter()
            if workers == 1:
                results = list(map(worker, tasks))
            else:
                with ProcessPoolExecutor(
                    max_workers=workers, mp_context=multiprocessing.get_context("spawn")
                ) as pool:
                    results = list(pool.map(worker, tasks, chunksize=1))
            elapsed = time.perf_counter() - started
            metrics = [r["metrics"] for r in results]
            if reference is None:
                reference = metrics
            assert metrics == reference, "Parallel execution changed results"
            item = {
                "workers": workers,
                "runs": args.jobs,
                "wall_seconds": elapsed,
                "runs_per_second": args.jobs / elapsed,
                "projected_100000_hours": elapsed / args.jobs * 100000 / 3600,
                "includes_pool_startup": True,
                "includes_summary_json": True,
                "timings": results,
            }
            report["parallel"].append(item)
            save()
            print(
                "Throughput",
                json.dumps({k: v for k, v in item.items() if k != "timings"}),
                flush=True,
            )


if __name__ == "__main__":
    main()
