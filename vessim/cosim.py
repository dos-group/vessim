from __future__ import annotations

from copy import copy
from typing import Optional, Literal

import mosaik  # type: ignore
import mosaik_api_v3  # type: ignore

from vessim.actor import ActorBase
from vessim.controller import Controller
from vessim.storage import Storage
from vessim.policy import MicrogridPolicy, DefaultMicrogridPolicy
from vessim._util import Clock, disable_rt_warnings


class Microgrid:
    def __init__(
        self,
        world: mosaik.World,
        clock: Clock,
        actors: list[ActorBase],
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
            actor_sim = world.start(
                "Actor", sim_id=actor.name, clock=clock, step_size=actor_step_size
            )
            # We initialize all actors before the grid simulation to make sure that
            # there is already a valid p_delta at step 0
            actor_entity = actor_sim.Actor(actor=actor)
            actor_names_and_entities.append((actor.name, actor_entity))

        grid_sim = world.start("Grid", step_size=step_size)
        grid_entity = grid_sim.Grid()
        for actor_name, actor_entity in actor_names_and_entities:
            world.connect(actor_entity, grid_entity, "p")

        controller_entities = []
        for controller in controllers:
            controller.start(self)
            controller_step_size = controller.step_size if controller.step_size else step_size
            if controller_step_size % step_size != 0:
                raise ValueError("Controller step size has to be a multiple of grids step size.")
            controller_sim = world.start(
                "Controller", sim_id=controller.name, clock=clock, step_size=controller_step_size
            )
            controller_entity = controller_sim.Controller(controller=controller)
            world.connect(grid_entity, controller_entity, "p_delta")
            for actor_name, actor_entity in actor_names_and_entities:
                world.connect(actor_entity, controller_entity, ("state", f"actor.{actor_name}"))
            controller_entities.append(controller_entity)

        storage_sim = world.start("Storage", step_size=step_size)
        storage_entity = storage_sim.Storage(storage=storage, policy=policy)
        world.connect(grid_entity, storage_entity, "p_delta")
        initial_state = {}
        initial_state["policy"] = policy.state()
        if storage:
            initial_state["storage"] = storage.state()
        for controller_entity in controller_entities:
            world.connect(controller_entity, storage_entity, "set_parameters")
            world.connect(
                storage_entity,
                controller_entity,
                "e",
                time_shifted=True,
                initial_data={"e": 0.0},
            )
            world.connect(
                storage_entity,
                controller_entity,
                "state",
                time_shifted=True,
                initial_data={"state": initial_state},
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
        for actor in self.actors:
            actor.finalize()


class Environment:
    COSIM_CONFIG: mosaik.SimConfig = {
        "Actor": {"python": "vessim.actor:_ActorSim"},
        "Controller": {"python": "vessim.controller:_ControllerSim"},
        "Grid": {"python": "vessim.cosim:_GridSim"},
        "Storage": {"python": "vessim.cosim:_StorageSim"},
    }

    def __init__(self, sim_start):
        self.clock = Clock(sim_start)
        self.microgrids = []
        self.world = mosaik.World(self.COSIM_CONFIG, skip_greetings=True)

    def add_microgrid(
        self,
        actors: list[ActorBase],
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
        behind_threshold: float = float("inf"),
    ):
        if until is None:
            # there is no integer representing infinity in python
            until = float("inf")  # type: ignore
        assert until is not None
        if rt_factor:
            disable_rt_warnings(behind_threshold)
        try:
            self.world.run(until=until, rt_factor=rt_factor, print_progress=print_progress)
        except Exception:
            for microgrid in self.microgrids:
                microgrid.finalize()
            raise


class _GridSim(mosaik_api_v3.Simulator):
    META = {
        "type": "time-based",
        "models": {
            "Grid": {
                "public": True,
                "params": [],
                "attrs": ["p", "p_delta"],
            },
        },
    }

    def __init__(self):
        super().__init__(self.META)
        self.eid = "Grid"
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
        assert self.step_size is not None
        return time + self.step_size

    def get_data(self, outputs):
        return {self.eid: {"p_delta": self.p_delta}}


class _StorageSim(mosaik_api_v3.Simulator):
    META = {
        "type": "time-based",
        "models": {
            "Storage": {
                "public": True,
                "params": ["storage", "policy"],
                "attrs": ["p_delta", "set_parameters", "e", "state"],
            },
        },
    }

    def __init__(self) -> None:
        super().__init__(self.META)
        self.eid: str = "Storage"

    def init(self, sid: str, time_resolution: float = 1.0, **sim_params):
        self.step_size: int = sim_params["step_size"]
        self.e: float = 0.0
        self.state: dict = {}
        return self.meta

    def create(self, num: int, model, **model_params):
        assert num == 1, "Only one instance per simulation is supported"
        self.storage: Optional[Storage] = model_params["storage"]
        self.policy: MicrogridPolicy = model_params["policy"]
        return [{"eid": self.eid, "type": model}]

    def step(self, time, inputs, max_advance):
        p_delta = list(inputs[self.eid]["p_delta"].values())[0]
        if "set_parameters" in inputs[self.eid].keys():
            for parameters in inputs[self.eid]["set_parameters"].values():
                for key, value in parameters.items():
                    key_split = key.split(":", 1)
                    if key_split[0] == "policy":
                        self.policy.set_parameter(key_split[1], value)
                    elif key_split[0] == "storage":
                        assert self.storage is not None
                        self.storage.set_parameter(key_split[1], value)
                    else:
                        raise ValueError(
                            f"Invalid parameter: {key}. Has to start with 'policy:' or 'storage:'."
                        )

        self.e += self.policy.apply(p_delta, duration=self.step_size, storage=self.storage)
        self.state["policy"] = self.policy.state()
        if self.storage:
            self.state["storage"] = self.storage.state()
        return time + self.step_size

    def get_data(self, outputs):
        return {self.eid: {"e": self.e, "state": self.state}}
