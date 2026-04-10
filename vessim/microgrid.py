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
        self.grid_signals = grid_signals
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
            # We initialize all actors before the microgrid simulation to make sure
            # that there is already a valid p_delta at step 0
            self.actor_entities[actor.name] = actor_sim.Actor(actor=actor)

        microgrid_sim = world.start(
            "Microgrid",
            sim_id=f"{self.name}.microgrid",
            step_size=step_size,
            grid_signals=grid_signals,
            sim_start=clock.sim_start,
        )
        self.entity = microgrid_sim.Microgrid(
            dispatchables=dispatchables, policy=policy,
        )
        for actor_entity in self.actor_entities.values():
            world.connect(actor_entity, self.entity, "power")

    def finalize(self):
        """Clean up in case the simulation was interrupted.

        Mosaik already has a cleanup functionality but this is an additional safety net
        in case the user interrupts the simulation before entering the mosiak event loop.
        """
        for actor in self.actors:
            actor.finalize()


class _MicrogridSim(mosaik_api_v3.Simulator):
    """Mosaik simulator that aggregates actor power and dispatches to flexible resources."""

    META = {
        "type": "time-based",
        "models": {
            "Microgrid": {
                "public": True,
                "params": ["dispatchables", "policy", "grid_signals"],
                "attrs": [
                    "power",
                    "p_delta",
                    "grid_signals",
                    "p_grid",
                    "dispatch_states",
                    "policy_state",
                ],
            },
        },
    }

    def __init__(self):
        super().__init__(self.META)
        self.eid = "Microgrid"
        self.step_size = None
        self.grid_signals: Optional[dict[str, Signal]] = None
        self.p_delta = 0.0
        self.p_grid = 0.0
        self.dispatch_states: dict = {}
        self.policy_state: dict = {}

    def init(self, sid, time_resolution=1.0, **sim_params):
        self.step_size = sim_params["step_size"]
        self.grid_signals = sim_params.get("grid_signals")
        self.sim_start = sim_params["sim_start"]
        return self.meta

    def create(self, num, model, **model_params):
        assert num == 1, "Only one instance per simulation is supported"
        self.dispatchables = model_params["dispatchables"]
        self.policy = model_params["policy"]
        return [{"eid": self.eid, "type": model}]

    def step(self, time, inputs, max_advance):
        assert self.step_size is not None

        # Phase 1: Advance dispatchable state from previous round's power setpoints
        for d in self.dispatchables:
            d.step(self.step_size)

        # Phase 2: Aggregate actor power into p_delta
        self.p_delta = sum(inputs[self.eid]["power"].values())

        # Phase 3: Resolve grid signals at current time
        if self.grid_signals:
            current_dt = self.sim_start + timedelta(seconds=time)
            self._resolved_grid_signals = {
                name: signal.now(at=current_dt)
                for name, signal in self.grid_signals.items()
            }
        else:
            self._resolved_grid_signals = None

        # Phase 4: Dispatch policy allocates new power setpoints
        self.p_grid = self.policy.apply(
            self.p_delta,
            duration=self.step_size,
            dispatchables=self.dispatchables,
            grid_signals=self._resolved_grid_signals,
        )

        self.policy_state = self.policy.state()
        self.dispatch_states = {d.name: d.state() for d in self.dispatchables}

        return time + self.step_size

    def get_data(self, outputs):
        return {
            self.eid: {
                "p_delta": self.p_delta,
                "grid_signals": self._resolved_grid_signals,
                "p_grid": self.p_grid,
                "dispatch_states": self.dispatch_states,
                "policy_state": self.policy_state,
            }
        }
