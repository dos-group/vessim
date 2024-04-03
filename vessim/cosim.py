from __future__ import annotations

import pickle
from copy import copy
from typing import Optional, Literal
from abc import ABC, abstractmethod

import mosaik  # type: ignore
import mosaik_api_v3  # type: ignore

from vessim.actor import Actor
from vessim.controller import Controller
from vessim.storage import Storage
from vessim._util import Clock


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
            controller.start()
            controller_step_size = controller.step_size if controller.step_size else step_size
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
                "e_delta",
                time_shifted=True,
                initial_data={"e_delta": 0.0},
            )

    def pickle(self) -> bytes:
        """Returns a Dict with the current state of the microgrid for monitoring."""
        cp = copy(self)
        cp.controllers = []  # controllers are not needed and often not pickleable
        return pickle.dumps(cp)

    def finalize(self):
        """Clean up in case the simulation was interrupted.

        Mosaik already has a cleanup functionality but this is an additional safety net
        in case the user interrupts the simulation before entering the mosiak event loop.
        """
        for controller in self.controllers:
            controller.finalize()


class MicrogridPolicy(ABC):
    """Policy that describes how the microgrid deals with specific power deltas."""

    @abstractmethod
    def apply(self, p_delta: float, duration: int, storage: Optional[Storage]) -> float:
        """"""

    @abstractmethod
    def state(self) -> dict:
        """Returns information about the current state of the storage policy as dictionary."""


class DefaultMicrogridPolicy(MicrogridPolicy):
    """Policy that is used as default for simulations.

    Args:
        mode: Defines the mode that the microgrid operates in. In `grid-connected` mode, the
            microgrid can draw power from and feed power to the utility grid at will, whereas
            in `islanded` mode, the microgrid has to rely on its own energy resources.
            Default is `grid-connected`.
        grid-power: Additional power that can be specified to charge/discharge microgrid storage
            (e.g. grid power of 5 would charge the battery at 5W on top of the overall energy delta
            everytime the policy is applied).
    """

    def __init__(
        self,
        mode: Literal["grid-connected", "islanded"] = "grid-connected",
        grid_power: float = 0,
    ):
        self.mode = mode
        self.grid_power = grid_power

    def apply(self, p_delta: float, duration: int, storage: Optional[Storage]) -> float:
        energy_delta = p_delta * duration
        if self.mode == "grid-connected" and storage is not None:
            energy_delta += self.grid_power * duration
            energy_delta -= storage.update(self.grid_power + p_delta, duration)
        elif self.mode == "islanded":
            # TODO What should be done when there is excess energy in islanded mode?
            if storage:
                energy_delta -= storage.update(p_delta, duration)
            if energy_delta < 0.0:
                raise RuntimeError("Not enough energy available to operate in islanded mode.")
            energy_delta = 0.0
        return energy_delta

    def state(self) -> dict:
        """Returns current mode and grid_power value."""
        return {
            "mode": self.mode,
            "grid_power": self.grid_power,
        }


class Environment:
    COSIM_CONFIG = {
        "Actor": {"python": "vessim.actor:_ActorSim"},
        "Aggregator": {"python": "vessim.aggregator: _AggregatorSim"},
        "Controller": {"python": "vessim.controller:_ControllerSim"},
        "Grid": {"python": "vessim.cosim:_GridSim"},
    }

    def __init__(self, sim_start):
        self.clock = Clock(sim_start)
        self.microgrids = []
        self.world = mosaik.World(self.COSIM_CONFIG)  # type: ignore

    def add_microgrid(
        self,
        actors: Optional[list[Actor]] = None,
        controllers: Optional[list[Controller]] = None,
        storage: Optional[Storage] = None,
        policy: Optional[MicrogridPolicy] = None,
        step_size: int = 1,  # global default
    ):
        microgrid = Microgrid(
            self.world,
            self.clock,
            actors if actors is not None else [],
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
    ):
        if until is None:
            # there is no integer representing infinity in python
            until = float("inf") # type: ignore
        try:
            self.world.run(
                until=until, rt_factor=rt_factor, print_progress=print_progress
            )
        except Exception as e:
            if str(e).startswith("Simulation too slow for real-time factor"):
                return
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
                "attrs": ["p_delta", "state"],
            },
        },
    }

    def __init__(self):
        super().__init__(self.META)
        self.eid = "Grid"
        self.step_size = None
        self.storage = None
        self.policy = None

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
        self.e_delta = self.policy.apply(self.storage, p_delta, self.step_size)
        return time + self.step_size

    def get_data(self, outputs):
        return {self.eid: {"e_delta": self.e_delta}}
