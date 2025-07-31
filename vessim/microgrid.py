from __future__ import annotations

from typing import TYPE_CHECKING, Optional, TypedDict

import mosaik
import mosaik_api_v3

if TYPE_CHECKING:
    from vessim.actor import Actor
    from vessim.policy import MicrogridPolicy
    from vessim.storage import Storage
    from vessim._util import Clock
    from vessim.signal import Signal


class MicrogridState(TypedDict):
    """State of a microgrid.

    This state is passed to controllers on every step.
    """

    p_delta: float  # Current power delta in W
    p_grid: float  # Last step's power exchange with the public grid in W
    actor_states: dict[str, dict]  # States of all actors in the microgrid
    policy_state: dict  # State of the microgrid policy
    storage_state: Optional[dict]  # State of the storage, if available
    grid_signals: Optional[dict[str, float]]  # Current grid signals, if available


class Microgrid:
    def __init__(
        self,
        world: mosaik.World,
        clock: Clock,
        step_size: int,
        actors: list[Actor],
        policy: MicrogridPolicy,
        storage: Optional[Storage] = None,
        grid_signals: Optional[dict[str, Signal]] = None,
        name: Optional[str] = None,
    ):
        self.step_size = step_size
        self.actors = actors
        self.policy = policy
        self.storage = storage
        self.name = name or f"microgrid_{id(self)}"

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
            "Grid", sim_id=f"{self.name}.grid", step_size=step_size, grid_signals=grid_signals
        )
        self.grid_entity = grid_sim.Grid()
        for actor_name, actor_entity in self.actor_entities.items():
            world.connect(actor_entity, self.grid_entity, "p")

        storage_sim = world.start("Storage", sim_id=f"{self.name}.storage", step_size=step_size)
        self.storage_entity = storage_sim.Storage(storage=storage, policy=policy)
        world.connect(self.grid_entity, self.storage_entity, "p_delta")

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
                "attrs": ["p", "p_delta", "grid_signals"],
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
        return self.meta

    def create(self, num, model, **model_params):
        assert num == 1, "Only one instance per simulation is supported"
        return [{"eid": self.eid, "type": model}]

    def step(self, time, inputs, max_advance):
        self.p_delta = sum(inputs[self.eid]["p"].values())
        assert self.step_size is not None
        return time + self.step_size

    def get_data(self, outputs):
        grid_signals = (
            {name: signal.now() for name, signal in self.grid_signals.items()}
            if self.grid_signals else None
        )
        return {self.eid: {"p_delta": self.p_delta, "grid_signals": grid_signals}}
