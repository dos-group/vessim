from __future__ import annotations

from copy import copy
from typing import Optional, Literal

import mosaik  # type: ignore
import mosaik_api_v3  # type: ignore

from vessim.actor import Actor
from vessim.controller import Controller
from vessim.storage import Storage
from vessim.policy import MicrogridPolicy, DefaultMicrogridPolicy
from vessim._util import Clock, disable_rt_warnings


class Microgrid:
    def __init__(
        self,
        world: mosaik.World,
        clock: Clock,
        actors: list[Actor],
        controllers: list[Controller],
        policy: MicrogridPolicy,
        storage: Optional[Storage] = None,
        step_size: int = 1,  # global default
    ):
        self.actors = actors
        self.controllers = controllers
        self.storage = storage
        self.policy = policy
        self.step_size = step_size

        actor_names_and_entities = []
        for actor in actors:
            actor_step_size = actor.step_size if actor.step_size else step_size
            if actor_step_size % step_size != 0:
                raise ValueError("Actor step size has to be a multiple of grids step size.")
            actor_sim = world.start("Actor", clock=clock, step_size=actor_step_size)
            # We initialize all actors before the grid simulation to make sure that
            # there is already a valid p_delta at step 0
            actor_entity = actor_sim.Actor(actor=actor)
            actor_names_and_entities.append((actor.name, actor_entity))

        aggregator_sim = world.start("Aggregator", step_size=step_size)
        aggregator_entity = aggregator_sim.Aggregator()
        for actor_name, actor_entity in actor_names_and_entities:
            world.connect(actor_entity, aggregator_entity, "p")

        controller_entities = []
        for controller in controllers:
            controller.start(self)
            controller_step_size = controller.step_size if controller.step_size else step_size
            if controller_step_size % step_size != 0:
                raise ValueError("Controller step size has to be a multiple of grids step size.")
            controller_sim = world.start("Controller", clock=clock, step_size=controller_step_size)
            controller_entity = controller_sim.Controller(controller=controller)
            world.connect(aggregator_entity, controller_entity, "p_delta")
            for actor_name, actor_entity in actor_names_and_entities:
                world.connect(
                    actor_entity, controller_entity, ("state", f"actor.{actor_name}")
                )
            controller_entities.append(controller_entity)

        grid_sim = world.start("Grid", step_size=step_size)
        grid_entity = grid_sim.Grid(storage=storage, policy=policy)
        world.connect(aggregator_entity, grid_entity, "p_delta")
        for controller_entity in controller_entities:
            world.connect(
                grid_entity,
                controller_entity,
                "e",
                time_shifted=True,
                initial_data={"e": 0.0},
            )

    def __getstate__(self) -> dict:
        """Returns a Dict with the current state of the microgrid for monitoring."""
        state = copy(self.__dict__)
        state["controllers"] = []  # controllers are not needed and often not pickleable
        state["actors"] = []  # actor info can be supplied through Actor.state()
        return state

    def finalize(self):
        """Clean up in case the simulation was interrupted.

        Mosaik already has a cleanup functionality but this is an additional safety net
        in case the user interrupts the simulation before entering the mosiak event loop.
        """
        for controller in self.controllers:
            controller.finalize()


class Environment:
    COSIM_CONFIG = {
        "Actor": {"python": "vessim.actor:_ActorSim"},
        "Aggregator": {"python": "vessim.cosim:_AggregatorSim"},
        "Controller": {"python": "vessim.controller:_ControllerSim"},
        "Grid": {"python": "vessim.cosim:_GridSim"},
    }

    def __init__(self, sim_start):
        self.clock = Clock(sim_start)
        self.microgrids = []
        self.world = mosaik.World(self.COSIM_CONFIG)  # type: ignore

    def add_microgrid(
        self,
        actors: list[Actor],
        controllers: Optional[list[Controller]] = None,
        storage: Optional[Storage] = None,
        policy: Optional[MicrogridPolicy] = None,
        step_size: int = 1,  # global default
    ):
        if not actors:
            raise ValueError("There should be at least one actor in the Microgrid.")

        microgrid = Microgrid(
            self.world,
            self.clock,
            actors,
            controllers if controllers is not None else [],
            policy if policy is not None else DefaultMicrogridPolicy(),
            storage,
            step_size,
        )
        self.microgrids.append(microgrid)
        return microgrid

    def run(
        self,
        until: Optional[int] = None,
        rt_factor: Optional[float] = None,
        print_progress: bool | Literal["individual"] = True,
        behind_threshold: float = 0.01
    ):
        if until is None:
            # there is no integer representing infinity in python
            until = float("inf") # type: ignore
        if rt_factor:
            disable_rt_warnings(behind_threshold)
        try:
            self.world.run(
                until=until, rt_factor=rt_factor, print_progress=print_progress
            )
        except Exception:
            for microgrid in self.microgrids:
                microgrid.finalize()
            raise


class _AggregatorSim(mosaik_api_v3.Simulator):
    META = {
        "type": "time-based",
        "models": {
            "Aggregator": {
                "public": True,
                "params": [],
                "attrs": ["p", "p_delta"],
            },
        },
    }

    def __init__(self):
        super().__init__(self.META)
        self.eid = "Aggregator"
        self.step_size = None
        self.p_delta = 0.0

    def init(self, sid, time_resolution=1.0, **sim_params):
        self.step_size = sim_params["step_size"]
        return self.meta

    def create(self, num, model, **model_params):
        assert num == 1, "Only one instance per simulation is supported"
        return [{"eid": self.eid, "type": model}]

    def step(self, time, inputs, max_advance):
        self.p_delta = sum(inputs[self.eid]["p"].values())
        return time + self.step_size

    def get_data(self, outputs):
        return {self.eid: {"p_delta": self.p_delta}}


class _GridSim(mosaik_api_v3.Simulator):
    META = {
        "type": "time-based",
        "models": {
            "Grid": {
                "public": True,
                "params": ["storage", "policy"],
                "attrs": ["p_delta", "e"],
            },
        },
    }

    def __init__(self):
        super().__init__(self.META)
        self.eid = "Grid"
        self.step_size = None
        self.storage = None
        self.policy = None
        self.e = 0.0

    def init(self, sid, time_resolution=1.0, **sim_params):
        self.step_size = sim_params["step_size"]
        return self.meta

    def create(self, num, model, **model_params):
        assert num == 1, "Only one instance per simulation is supported"
        self.storage = model_params["storage"]
        self.policy = model_params["policy"]
        return [{"eid": self.eid, "type": model}]

    def step(self, time, inputs, max_advance):
        p_delta = list(inputs[self.eid]["p_delta"].values())[0]
        self.e += self.policy.apply(p_delta, duration=self.step_size, storage=self.storage)
        return time + self.step_size

    def get_data(self, outputs):
        return {self.eid: {"e": self.e}}
