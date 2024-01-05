import pickle
from copy import copy
from typing import Optional, Union, Literal, List, Dict

import mosaik
import mosaik_api

from vessim import TimeSeriesApi
from vessim._util import Clock
from vessim.actor import Actor
from vessim.controller import Controller
from vessim.storage import Storage, StoragePolicy, DefaultStoragePolicy


class Microgrid:
    def __init__(
        self,
        actors: List[Actor],
        controllers: List[Controller],
        storage: Optional[Storage] = None,
        storage_policy: Optional[StoragePolicy] = None,
        zone: Optional[str] = None,
    ):
        self.actors = actors
        self.controllers = controllers
        self.storage = storage
        self.storage_policy = storage_policy
        self.zone = zone

    def initialize(
        self,
        world: mosaik.World,
        clock: Clock,
        grid_signals: Dict[str, TimeSeriesApi]
    ):
        """Create co-simulation entities and connect them to world"""
        grid_sim = world.start("Grid")
        grid_entity = grid_sim.Grid(storage=self.storage, policy=self.storage_policy)

        controller_entities = []
        for controller in self.controllers:
            controller.start(self, clock, grid_signals)
            controller_sim = world.start("Controller", step_size=controller.step_size)
            controller_entity = controller_sim.Controller(controller=controller)
            world.connect(grid_entity, controller_entity, "p_delta")
            controller_entities.append(controller_entity)

        for actor in self.actors:
            actor_sim = world.start("Actor", clock=clock, step_size=actor.step_size)
            actor_entity = actor_sim.Actor(actor=actor)
            world.connect(actor_entity, grid_entity, "p")

            for controller_entity in controller_entities:
                world.connect(actor_entity, controller_entity, ("p", f"actor.{actor.name}.p"))
                world.connect(actor_entity, controller_entity, ("info", f"actor.{actor.name}.info"))

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


class Environment:
    COSIM_CONFIG = {
        "Actor": {
            "python": "vessim.cosim.actor:ActorSim",
        },
        "Controller": {
            "python": "vessim.cosim.controller:ControllerSim",
        },
        "Grid": {
            "python": "vessim.cosim.grid:GridSim"
        },
    }

    def __init__(self, sim_start):
        self.clock = Clock(sim_start)
        self.microgrids = []
        self.grid_signals = {}
        self.world = mosaik.World(self.COSIM_CONFIG)

    def add_microgrid(self, microgrid: Microgrid):
        # We do not yet instantiate the microgrids
        self.microgrids.append(microgrid)

    def add_grid_signal(self, name: str, grid_signal: TimeSeriesApi):
        if len(self.microgrids) > 0:
            raise RuntimeError("Add all grid signals before adding microgrids.")
        self.grid_signals[name] = grid_signal

    def run(
        self,
        until: int,
        rt_factor: Optional[float] = None,
        print_progress: Union[bool, Literal["individual"]] = True,
    ):
        try:
            for microgrid in self.microgrids:
                microgrid.initialize(self.world, self.clock, self.grid_signals)
            self.world.run(until=until, rt_factor=rt_factor, print_progress=print_progress)
        except Exception as e:
            if str(e).startswith("Simulation too slow for real-time factor"):
                return
            for microgrid in self.microgrids:
                microgrid.finalize()
            raise


class GridSim(mosaik_api.Simulator):
    META = {
        "type": "event-based",
        "models": {
            "Grid": {
                "public": True,
                "params": ["storage", "policy"],
                "attrs": ["p", "p_delta"],
            },
        },
    }

    def __init__(self):
        super().__init__(self.META)
        self.eid = "Grid"
        self.storage = None
        self.policy = None
        self.p_delta = 0.0
        self._last_step_time = 0

    def create(self, num, model, **model_params):
        assert num == 1, "Only one instance per simulation is supported"
        self.storage = model_params["storage"]
        self.policy = model_params["policy"]
        if self.policy is None:
            self.policy = DefaultStoragePolicy()
        return [{"eid": self.eid, "type": model}]

    def step(self, time, inputs, max_advance):
        duration = time - self._last_step_time
        self._last_step_time = time
        if duration == 0:
            return
        p_delta = sum(inputs[self.eid]["p"].values())
        if self.storage is None:
            self.p_delta = p_delta
        else:
            self.p_delta = self.policy.apply(self.storage, p_delta, duration)

    def get_data(self, outputs):
        return {self.eid: {"p_delta": self.p_delta}}