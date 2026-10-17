from __future__ import annotations

from copy import deepcopy
from typing import Optional, TypedDict

import numpy as np

from vessim.actor import Actor
from vessim._util import require_balanced, require_finite
from vessim.dispatchable import Dispatchable, GridConnection
from vessim.dispatch_policy import DispatchPolicy
from vessim.signal import Signal


class MicrogridState(TypedDict):
    """Observation at a tick, after dispatch and before controllers execute."""

    p_delta: float
    p_grid: float
    actor_states: dict[str, dict]
    policy_state: dict
    dispatch_states: dict[str, dict]
    grid_signals: Optional[dict[str, float]]


_IMMUTABLE_SCALARS = (str, int, float, bool, bytes, type(None), np.float64)


def _snapshot(state: dict) -> dict:
    # Built-in observations are flat dictionaries of immutable scalars. Avoid
    # deepcopy's recursive bookkeeping there, retaining it for custom state.
    if all(type(value) in _IMMUTABLE_SCALARS for value in state.values()):
        return state.copy()
    return deepcopy(state)


class Microgrid:
    """Energy-system models and current state, independent of an execution backend.

    Usually constructed through :meth:`Environment.add_microgrid`. Powers are
    in W. Actor generation is positive and consumption negative. Dispatchable
    supply/import is negative. Absorption/export is positive.

    Args:
        step_size: Positive integer sampling interval in seconds.
        actors: Exogenous loads and generators.
        dispatchables: Controllable resources, in dispatch order. Include a
            GridConnection explicitly for grid-connected operation. Without one,
            the microgrid is islanded.
        policy: Policy assigning the next power setpoints.
        grid_signals: Context such as price or carbon intensity.
        name: Unique name within the environment.
        coords: Optional latitude and longitude for the viewer.
    """

    def __init__(
        self,
        step_size: int,
        actors: list[Actor],
        dispatchables: list[Dispatchable],
        policy: DispatchPolicy,
        grid_signals: Optional[dict[str, Signal]] = None,
        name: str = "microgrid",
        coords: Optional[tuple[float, float]] = None,
    ):
        self.step_size = step_size
        self.actors = list(actors)
        self.dispatchables = list(dispatchables)
        self.policy = policy
        self.grid_signals = dict(grid_signals) if grid_signals else None
        self.name = name
        self.coords = coords
        self.p_delta = 0.0
        self.p_grid = 0.0
        self._resolved_grid_signals: Optional[dict[str, float]] = None
        self._actor_states: dict[str, dict] = {}
        self._last_elapsed = 0.0
        self._validate()

    def _validate(self) -> None:
        if (
            isinstance(self.step_size, bool)
            or not isinstance(self.step_size, int)
            or self.step_size <= 0
        ):
            raise ValueError("step_size must be a positive integer number of seconds.")
        for group in (self.actors, self.dispatchables):
            names = [item.name for item in group]
            if any(not isinstance(n, str) or not n for n in names):
                raise ValueError("Component names must be nonempty strings.")
            if len(set(names)) != len(names):
                raise ValueError("Component names must be unique within each microgrid.")
        for actor in self.actors:
            period = self.step_size if actor.step_size is None else actor.step_size
            if (
                isinstance(period, bool)
                or not isinstance(period, int)
                or period <= 0
                or period % self.step_size
            ):
                raise ValueError(
                    "Actor step size has to be a positive multiple of grid step size."
                )
        # Capture the final scenario configuration when Environment.prepare()
        # validates it, including changes made after add_microgrid().
        self._sampling = [(a, a.step_size or self.step_size) for a in self.actors]
        self._powers = {a.name: 0.0 for a in self.actors}

    def sample(self, elapsed: int) -> None:
        """Update due actors, holding slower actors' measurements between updates."""
        for actor, period in self._sampling:
            if elapsed % period == 0:
                power, state = actor.sample(elapsed)
                require_finite(power, f"Power from actor '{actor.name}' at {elapsed}s")
                self._powers[actor.name] = power
                self._actor_states[actor.name] = state

    def advance(
        self, elapsed: int, external_power: float = 0.0, duration: Optional[float] = None
    ) -> None:
        """Integrate previous setpoints and dispatch the next interval.

        Tick zero observes the initial state without integrating any energy.
        ``duration`` clips dispatch to the remaining time in the final interval.
        Call ``finish(until)`` to integrate that interval without another dispatch.
        """
        self.finish(elapsed)
        require_finite(external_power, f"External power for microgrid '{self.name}'")
        self.p_delta = sum(self._powers.values())
        if external_power:
            self.p_delta += external_power
        self._resolved_grid_signals = (
            {name: signal.at(elapsed) for name, signal in self.grid_signals.items()}
            if self.grid_signals
            else None
        )
        require_finite(self.p_delta, f"Total power for microgrid '{self.name}'")
        for name, value in (self._resolved_grid_signals or {}).items():
            require_finite(value, f"Grid signal '{name}' at {elapsed}s")
        interval = self.step_size if duration is None else duration
        bounds = [d._validated_range(interval) for d in self.dispatchables]
        self.policy.apply(
            self.p_delta,
            duration=interval,
            dispatchables=list(self.dispatchables),
            grid_signals=self._resolved_grid_signals,
        )
        for d, (lo, hi) in zip(self.dispatchables, bounds):
            require_finite(d.current_power, f"Power setpoint for '{d.name}'")
            if not lo <= d.current_power <= hi:
                raise ValueError(f"Policy set power outside the feasible range for '{d.name}'.")
        require_balanced(self.p_delta, (d.current_power for d in self.dispatchables))
        self.p_grid = sum(
            d.current_power for d in self.dispatchables if isinstance(d, GridConnection)
        )
        require_finite(self.p_grid, f"Grid power for '{self.name}'")

    def finish(self, elapsed: float) -> None:
        """Integrate held setpoints up to elapsed time, without sampling or dispatch."""
        require_finite(elapsed, "Integration time")
        duration = elapsed - self._last_elapsed
        if duration < 0:
            raise ValueError("Microgrid integration time must not move backwards.")
        if duration > 0:
            for dispatchable in self.dispatchables:
                dispatchable.step(duration)
        self._last_elapsed = elapsed

    def state(self) -> MicrogridState:
        """Return a detached observation, safe to retain across subsequent ticks."""
        return MicrogridState(
            p_delta=self.p_delta,
            p_grid=self.p_grid,
            actor_states={name: _snapshot(state) for name, state in self._actor_states.items()},
            policy_state=_snapshot(self.policy.state()),
            dispatch_states={d.name: _snapshot(d.state()) for d in self.dispatchables},
            grid_signals=(
                dict(self._resolved_grid_signals)
                if self._resolved_grid_signals is not None
                else None
            ),
        )

    def finalize(self) -> None:
        """Finalize actors and grid signals when used outside an Environment."""
        for actor in self.actors:
            actor.finalize()
        actor_signals = {id(a.signal) for a in self.actors}
        for signal in (self.grid_signals or {}).values():
            if id(signal) not in actor_signals:
                signal.finalize()
