"""Reproducible backend comparison using public Vessim APIs.

Run from the repository: python benchmarks/run.py --backend native --output result.json
"""

from __future__ import annotations

import argparse
import cProfile
import gc
import hashlib
import importlib.metadata
import json
import platform
import statistics
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from loguru import logger
import vessim as vs

CASES = ("static", "traces", "csv", "many_grids", "mixed_rates", "feedback")


def environment_info():
    versions = {}
    for package in ("vessim", "numpy", "pandas", "mosaik"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    return {"python": platform.python_version(), "platform": platform.platform(), **versions}


class Feedback(vs.Controller):
    def start(self, environment):
        self.grids = environment.microgrids

    def step(self, now, microgrid_states):
        for grid in self.grids.values():
            grid.policy.charge_power = 100 if now.minute % 2 else -100


def build(backend, case, traces, directory):
    env = vs.Environment(sim_start="2026-01-01", step_size=60, backend=backend)
    for i in range(10 if case == "many_grids" else 1):
        traced = case != "static"
        env.add_microgrid(
            name=f"grid{i}",
            actors=[
                vs.Producer(
                    "solar",
                    traces["solar"] if traced else 900,
                    step_size=180 if case == "mixed_rates" else None,
                ),
                vs.Consumer("load", traces["load"] if traced else 600),
            ],
            dispatchables=[
                vs.SimpleBattery("battery", 1500, initial_soc=0.5, min_soc=0.1),
                vs.GridConnection(),
            ],
            grid_signals={"carbon": traces["carbon"]} if traced else None,
        )
    if case == "feedback":
        env.add_controller(Feedback())
    memory = vs.Recorder(metrics=False)
    env.add_controller(memory)
    if case == "csv":
        env.add_controller(vs.Recorder(directory, metrics=False))
    return env, memory


def digest(memory):
    rows = [(str(t), value) for t, value in memory.log.items()]
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=["native", "mosaik"], default="native")
    parser.add_argument("--steps", type=int, default=1000)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", type=Path, help="Directory for per-workload cProfile files")
    args = parser.parse_args()
    if args.steps < 1 or args.repeats < 1:
        parser.error("steps and repeats must be positive")
    logger.remove()
    results = {
        "backend": args.backend,
        **environment_info(),
        "cases": {},
    }
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        if args.steps == 1000:
            (directory / "input.csv").write_bytes(
                Path(__file__).with_name("input.csv").read_bytes()
            )
        else:
            offsets = np.arange(args.steps + 1) * 60
            pd.DataFrame(
                {
                    "solar": 1200 * np.maximum(0, np.sin(offsets / 86400 * 2 * np.pi)),
                    "load": 600 + 100 * np.cos(offsets / 1800),
                    "carbon": 300 + 100 * np.sin(offsets / 3600),
                },
                index=offsets,
            ).to_csv(directory / "input.csv")
        t0 = time.perf_counter()
        traces = {
            c: vs.Trace.from_csv(directory / "input.csv", column=c)
            for c in ("solar", "load", "carbon")
        }
        results["trace_load_seconds"] = time.perf_counter() - t0
        for case in CASES:
            steps = max(1, args.steps // 5) if case == "many_grids" else args.steps
            timings, setups = [], []
            checksums = set()
            for repeat in range(args.repeats):
                gc.collect()
                t0 = time.perf_counter()
                env, memory = build(args.backend, case, traces, directory / f"{case}-{repeat}")
                setups.append(time.perf_counter() - t0)
                t0 = time.perf_counter()
                env.run(until=steps * 60, print_progress=False)
                timings.append(time.perf_counter() - t0)
                checksum = digest(memory)
                checksums.add(checksum)
            if len(checksums) != 1:
                raise RuntimeError(f"Repeated {case} runs produced different trajectories")
            gc.collect()
            tracemalloc.start()
            env, memory = build(args.backend, case, traces, directory / f"{case}-memory")
            env.run(until=steps * 60, print_progress=False)
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            results["cases"][case] = {
                "steps": steps,
                "run_seconds": statistics.median(timings),
                "setup_seconds": statistics.median(setups),
                "runs": timings,
                "peak_traced_bytes": peak,
                "trajectory_sha256": checksum,
            }
            print(case, results["cases"][case], flush=True)
            if args.profile:
                args.profile.mkdir(parents=True, exist_ok=True)
                env, _ = build(args.backend, case, traces, directory / f"{case}-profile")
                profiler = cProfile.Profile()
                profiler.runcall(env.run, until=steps * 60, print_progress=False)
                profiler.dump_stats(str(args.profile / f"{case}.prof"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
