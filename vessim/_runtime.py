"""The shared Vessim tick; execution backends only arrange when it is called."""

from __future__ import annotations

import time
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional

from loguru import logger

from vessim.microgrid import MicrogridState

if TYPE_CHECKING:
    from vessim.environment import Environment


@dataclass(frozen=True)
class RunResult:
    """Final state and execution timing returned by Environment.run().

    Attributes:
        steps: Number of simulation ticks executed.
        until: Simulation horizon in elapsed seconds.
        last_time: Timestamp of the last tick, or None for a zero-length run.
        states: Microgrid observations keyed by name. Dispatchable states are
            advanced to the horizon. Actor power, grid signals, and dispatch
            values come from the last tick.
        wall_time: Execution time in seconds.

    Use Recorder for time series and aggregate metrics. No extra observation
    or controller call occurs at the horizon.
    """

    steps: int
    until: float
    last_time: Optional[datetime]
    states: dict[str, MicrogridState]
    wall_time: float


class Runtime:
    def __init__(self, environment: Environment):
        self.environment = environment
        self.grids = tuple(environment.microgrids.values())
        self.steps = 0
        self.last_elapsed: Optional[int] = None
        self.states: dict[str, MicrogridState] = {}
        self.error: Optional[BaseException] = None
        self.started = 0.0
        self._last_warning = float("-inf")

    def pace(self, elapsed: float) -> None:
        if not self.environment.is_live:
            return
        delay = self.started + elapsed - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        elif -delay > self.environment.behind_threshold:
            now = time.monotonic()
            if now - self._last_warning >= max(1.0, self.environment.behind_threshold):
                logger.warning("Live simulation is {:.3f}s behind wall-clock time", -delay)
                self._last_warning = now

    def step(self, elapsed: int, external: Optional[dict[str, float]] = None) -> None:
        try:
            self.pace(elapsed)
            self.environment._start_signals()
            # All actors are sampled before any policy or controller can mutate them.
            for grid in self.grids:
                grid.sample(elapsed)
            for grid in self.grids:
                duration = min(grid.step_size, self.environment.until - elapsed)
                grid.advance(elapsed, (external or {}).get(grid.name, 0.0), duration)
            self.steps += 1
            self.last_elapsed = elapsed
            if self.environment.controllers or self.environment.backend == "mosaik":
                self.states = {grid.name: grid.state() for grid in self.grids}
            if self.environment.controllers:
                assert self.environment.sim_start is not None
                now = self.environment.sim_start + timedelta(seconds=elapsed)
                for controller in self.environment.controllers:
                    controller.step(now, self.states)
        except BaseException as exc:
            self.error = exc
            raise

    def finish(self, until: float) -> None:
        """Advance resources through the final interval without an extra tick."""
        if self.last_elapsed is not None:
            for grid in self.grids:
                grid.finish(until)
            self.states = {grid.name: grid.state() for grid in self.grids}

    def result(self, wall_time: float) -> RunResult:
        env = self.environment
        last_time = None
        if self.last_elapsed is not None:
            assert env.sim_start is not None
            last_time = env.sim_start + timedelta(seconds=self.last_elapsed)
            if not self.states:
                self.states = {grid.name: grid.state() for grid in self.grids}
        return RunResult(self.steps, env.until, last_time, deepcopy(self.states), wall_time)
