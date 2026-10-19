"""Direct execution of the shared tick, with no co-simulation scheduler."""
from __future__ import annotations

import sys
import time

from vessim._runtime import Runtime


def run(runtime: Runtime, until: float, print_progress: bool) -> None:
    elapsed = 0
    next_progress = 0.0
    while elapsed < until:
        runtime.step(elapsed)
        elapsed += runtime.environment.step_size
        if print_progress and time.monotonic() >= next_progress:
            print(f"\rSimulated {min(elapsed, until):g}s", end="", file=sys.stderr)
            next_progress = time.monotonic() + 0.25
    if print_progress:
        print(file=sys.stderr)
