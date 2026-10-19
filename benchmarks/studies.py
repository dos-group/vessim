"""Measure multi-run throughput and bounded versus trajectory result retention."""

from __future__ import annotations

import argparse
import gc
import json
import sys
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from loguru import logger
import vessim as vs
from benchmarks.run import environment_info


def scenario(trace, steps, backend, output):
    env = vs.Environment("2026-01-01", step_size=60, backend=backend)
    env.add_microgrid(
        [vs.Consumer("load", signal=trace)],
        [vs.SimpleBattery("battery", 1500, initial_soc=0.5), vs.GridConnection()],
        name="site",
    )
    if output == "metrics":
        env.add_controller(vs.Recorder(timeseries=False))
    elif output == "trajectory":
        env.add_controller(vs.Recorder())
    env.run(steps * 60)
    return env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=["native", "mosaik"], default="native")
    parser.add_argument("--runs", type=int, default=100)
    parser.add_argument("--steps", type=int, default=288)
    parser.add_argument("--memory-steps", nargs="+", type=int, default=[1000, 10000])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.runs < 1 or args.steps < 1 or any(n < 1 for n in args.memory_steps):
        parser.error("runs, steps, and memory-steps must be positive")
    logger.remove()
    data = pd.Series([500, 700, 600], index=[0, 3600, 7200])
    horizon = max(args.steps, *args.memory_steps) * 60
    if horizon > data.index[-1]:
        data.loc[horizon] = data.iloc[-1]
    trace = vs.Trace(data)
    result = {
        **environment_info(),
        "backend": args.backend,
        "runs": args.runs,
        "steps_per_run": args.steps,
    }
    scenario(trace, 1, args.backend, "metrics")  # Optional import warm-up.
    t0 = time.perf_counter()
    for _ in range(args.runs):
        scenario(trace, args.steps, args.backend, "metrics")
    result["total_seconds"] = time.perf_counter() - t0
    result["scenarios_per_second"] = args.runs / result["total_seconds"]
    result["memory"] = []
    for output in ("none", "metrics", "trajectory"):
        for steps in args.memory_steps:
            gc.collect()
            tracemalloc.start()
            env = scenario(trace, steps, args.backend, output)
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            result["memory"].append({"output": output, "steps": steps, "peak_traced_bytes": peak})
            del env
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
