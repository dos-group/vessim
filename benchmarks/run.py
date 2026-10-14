"""Reproducible backend comparison using public Vessim APIs.

Run from the repository: python benchmarks/run.py --backend native --output result.json
The legacy option runs against the pre-refactor checkout without a backend argument.
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


class Feedback(vs.Controller):
    def start(self, environment):
        self.grids = environment.microgrids

    def step(self, now, microgrid_states):
        for grid in self.grids.values():
            grid.policy.charge_power = 100 if now.minute % 2 else -100


def build(backend, case, traces, directory):
    kwargs = {} if backend == "legacy" else {"backend": backend}
    env = vs.Environment(sim_start="2026-01-01", step_size=60, **kwargs)
    for i in range(10 if case == "many_grids" else 1):
        traced = case != "static"
        env.add_microgrid(
            name=f"grid{i}",
            actors=[
                vs.Actor(
                    "solar",
                    traces["solar"] if traced else vs.StaticSignal(900),
                    step_size=180 if case == "mixed_rates" else None,
                ),
                vs.Actor(
                    "load", traces["load"] if traced else vs.StaticSignal(600), consumer=True
                ),
            ],
            dispatchables=[vs.SimpleBattery("battery", 1500, initial_soc=0.5, min_soc=0.1)],
            grid_signals={"carbon": traces["carbon"]} if traced else None,
        )
    if case == "feedback":
        env.add_controller(Feedback())
    memory = vs.MemoryLogger()
    env.add_controller(memory)
    if case == "csv":
        env.add_controller(vs.CsvLogger(directory))
    return env, memory


def digest(memory):
    rows = [(str(t), value) for t, value in memory.to_dict().items()]
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=["legacy", "native", "mosaik"], required=True)
    parser.add_argument("--steps", type=int, default=1000)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", type=Path)
    args = parser.parse_args()
    logger.remove()
    results = {
        "backend": args.backend,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "numpy": np.__version__,
        "mosaik": importlib.metadata.version("mosaik"),
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
        for case in ("static", "traces", "csv", "many_grids", "mixed_rates", "feedback"):
            steps = args.steps // 5 if case == "many_grids" else args.steps
            timings, setups = [], []
            for _ in range(args.repeats):
                gc.collect()
                t0 = time.perf_counter()
                env, memory = build(args.backend, case, traces, directory / "output")
                setups.append(time.perf_counter() - t0)
                t0 = time.perf_counter()
                env.run(until=steps * 60, print_progress=False)
                timings.append(time.perf_counter() - t0)
                checksum = digest(memory)
            gc.collect()
            tracemalloc.start()
            env, memory = build(args.backend, case, traces, directory / "output")
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
            env, _ = build(args.backend, "traces", traces, directory / "output")
            profiler = cProfile.Profile()
            profiler.runcall(env.run, until=args.steps * 60, print_progress=False)
            profiler.dump_stats(str(args.profile))
    args.output.write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
