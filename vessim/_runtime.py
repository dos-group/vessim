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
    """Compact result returned by a completed run; no trajectory is retained.

    ``states`` is the final tick's observation, before controller actions.
    ``until`` is the exclusive horizon in elapsed seconds; ``last_time`` is
    the timestamp of the last executed tick, or None for a zero-length run.
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
            # All actors are sampled before any policy or controller can mutate them.
            for grid in self.grids:
                grid.sample(elapsed)
            for grid in self.grids:
                grid.advance(elapsed, (external or {}).get(grid.name, 0.0))
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

    def result(self, wall_time: float) -> RunResult:
        env = self.environment
        last_time = None
        if self.last_elapsed is not None:
            assert env.sim_start is not None
            last_time = env.sim_start + timedelta(seconds=self.last_elapsed)
            if not self.states:
                self.states = {grid.name: grid.state() for grid in self.grids}
        return RunResult(self.steps, env.until, last_time, deepcopy(self.states), wall_time)
