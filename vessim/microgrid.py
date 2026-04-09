from __future__ import annotations

from typing import TYPE_CHECKING, Optional, TypedDict
from datetime import timedelta

import mosaik
import mosaik_api_v3

if TYPE_CHECKING:
    from vessim.actor import Actor
    from vessim.dispatch_policy import DispatchPolicy
    from vessim.dispatchable import Dispatchable
    from vessim._util import Clock
    from vessim.signal import Signal


class MicrogridState(TypedDict):
    """State of a microgrid.

    This state is passed to `Controller`s on every step.
    """

    p_delta: float  # Current power delta in W
    p_grid: float  # Last step's power exchange with the public grid in W
    actor_states: dict[str, dict]  # States of all actors in the microgrid
    policy_state: dict  # State of the microgrid dispatch policy
    dispatch_states: dict[str, dict]  # States of all dispatchables, keyed by name
    grid_signals: Optional[dict[str, float]]  # Current grid signals, if available


class Microgrid:
    """A simulated energy system.

    A microgrid is a collection of actors (exogenous consumers and producers),
    dispatchables (controllable resources like batteries), and a dispatch policy
    that governs their interaction. It can also be connected to the public grid.

    Args:
        world: The mosaik world instance.
        clock: The simulation clock.
        step_size: The step size of the simulation in seconds.
        actors: The exogenous actors in the microgrid.
        dispatchables: The dispatchable resources in the microgrid.
        policy: The `DispatchPolicy` that controls the microgrid.
        grid_signals: Optional signals from the public grid.
        name: Optional name for the microgrid.
        coords: Optional coordinates (latitude, longitude) for visualizing the
            microgrid's location in the dashboard.
    """

    def __init__(
        self,
        world: mosaik.World,
        clock: Clock,
        step_size: int,
        actors: list[Actor],
        dispatchables: list[Dispatchable],
        policy: DispatchPolicy,
        grid_signals: Optional[dict[str, Signal]] = None,
        name: Optional[str] = None,
        coords: Optional[tuple[float, float]] = None,
    ):
        self.step_size = step_size
        self.actors = actors
        self.dispatchables = dispatchables
        self.policy = policy
        self.name = name or f"microgrid_{id(self)}"
        self.coords = coords

        self.actor_entities = {}
        for actor in actors:
            actor_step_size = actor.step_size if actor.step_size else step_size
            if actor_step_size % step_size != 0:
                raise ValueError("Actor step size has to be a multiple of grids step size.")
            actor_sim = world.start(
                "Actor",
                sim_id=f"{self.name}.actor.{actor.name}",
                clock=clock,
                step_size=actor_step_size,
            )
            # We initialize all actors before the grid simulation to make sure that
            # there is already a valid p_delta at step 0
            self.actor_entities[actor.name] = actor_sim.Actor(actor=actor)

        grid_sim = world.start(
            "Grid",
            sim_id=f"{self.name}.grid",
            step_size=step_size,
            grid_signals=grid_signals,
            sim_start=clock.sim_start,
        )
        self.grid_entity = grid_sim.Grid()
        for actor_name, actor_entity in self.actor_entities.items():
            world.connect(actor_entity, self.grid_entity, "power")

        dispatch_sim = world.start("Dispatch", sim_id=f"{self.name}.dispatch", step_size=step_size)
        self.dispatch_entity = dispatch_sim.Dispatch(dispatchables=dispatchables, policy=policy)
        world.connect(self.grid_entity, self.dispatch_entity, "p_delta")
        world.connect(self.grid_entity, self.dispatch_entity, "grid_signals")

    def finalize(self):
        """Clean up in case the simulation was interrupted.

        Mosaik already has a cleanup functionality but this is an additional safety net
        in case the user interrupts the simulation before entering the mosiak event loop.
        """
        for actor in self.actors:
            actor.finalize()


class _GridSim(mosaik_api_v3.Simulator):
    META = {
        "type": "time-based",
        "models": {
            "Grid": {
                "public": True,
                "params": ["grid_signals"],
                "attrs": ["power", "p_delta", "grid_signals"],
            },
        },
    }

    def __init__(self):
        super().__init__(self.META)
        self.eid = "Grid"
        self.step_size = None
        self.grid_signals: Optional[dict[str, Signal]] = None
        self.p_delta = 0.0

    def init(self, sid, time_resolution=1.0, **sim_params):
        self.step_size = sim_params["step_size"]
        self.grid_signals = sim_params["grid_signals"]
        self.sim_start = sim_params["sim_start"]
        return self.meta

    def create(self, num, model, **model_params):
        assert num == 1, "Only one instance per simulation is supported"
        return [{"eid": self.eid, "type": model}]

    def step(self, time, inputs, max_advance):
        self._current_time = time
        self.p_delta = sum(inputs[self.eid]["power"].values())
        assert self.step_size is not None
        return time + self.step_size

    def get_data(self, outputs):
        if self.grid_signals:
            current_dt = self.sim_start + timedelta(seconds=self._current_time)
            grid_signals = {
                name: signal.now(at=current_dt)
                for name, signal in self.grid_signals.items()
            }
        else:
            grid_signals = None
        return {self.eid: {"p_delta": self.p_delta, "grid_signals": grid_signals}}
