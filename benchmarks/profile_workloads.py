"""Profile all representative workloads without treating instrumented time as speed."""

from __future__ import annotations

import argparse
import cProfile
import json
import pstats
import tempfile
from pathlib import Path

from run import build, vs, logger


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    logger.remove()
    traces = {
        column: vs.Trace.from_csv(Path(__file__).with_name("input.csv"), column=column)
        for column in ("solar", "load", "carbon")
    }
    profiles = {}
    with tempfile.TemporaryDirectory() as temp:
        for backend in ("native", "mosaik"):
            profiles[backend] = {}
            for case in ("static", "traces", "csv", "many_grids", "mixed_rates", "feedback"):
                env, _ = build(backend, case, traces, Path(temp))
                profiler = cProfile.Profile()
                profiler.runcall(env.run, until=(200 if case == "many_grids" else 1000) * 60)
                stats = pstats.Stats(profiler).strip_dirs()
                top = sorted(stats.stats.items(), key=lambda item: item[1][2], reverse=True)[:8]
                profiles[backend][case] = {
                    "calls": stats.total_calls,
                    "profile_seconds": stats.total_tt,
                    "top_self_time": [
                        {
                            "function": f"{key[0]}:{key[2]}",
                            "calls": value[1],
                            "self_seconds": value[2],
                        }
                        for key, value in top
                    ],
                }
    args.output.write_text(json.dumps(profiles, indent=2) + "\n")


if __name__ == "__main__":
    main()
