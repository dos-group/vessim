import pickle
from copy import copy
from typing import List, Optional, Dict, Union, Literal

import mosaik  # type: ignore

from vessim._signal import Signal
from vessim._util import Clock
from vessim.cosim import Actor, Controller, Storage, StoragePolicy


class Microgrid:
    def __init__(
        self,
        actors: Optional[List[Actor]] = None,
        controllers: Optional[List[Controller]] = None,
        storage: Optional[Storage] = None,
        storage_policy: Optional[StoragePolicy] = None,
        zone: Optional[str] = None,
        step_size: int = 1,  # global default
    ):
        self.actors = actors if actors is not None else []
        self.controllers = controllers if controllers is not None else []
        self.storage = storage
        self.storage_policy = storage_policy
        self.zone = zone
        self.step_size = step_size

    def initialize(
        self, world: mosaik.World, clock: Clock, grid_signals: Dict[str, Signal]
    ):
        """Create co-simulation entities and connect them to world."""
        grid_sim = world.start("Grid")
        grid_entity = grid_sim.Grid(storage=self.storage, policy=self.storage_policy)

        actor_names_and_entities = []
        for actor in self.actors:
            step_size = actor.step_size if actor.step_size else self.step_size
            actor_sim = world.start("Actor", clock=clock, step_size=step_size)
            actor_entity = actor_sim.Actor(actor=actor)
            world.connect(actor_entity, grid_entity, "p")
            actor_names_and_entities.append((actor.name, actor_entity))

        for controller in self.controllers:
            controller.init(self, clock, grid_signals)
            step_size = controller.step_size if controller.step_size else self.step_size
            controller_sim = world.start("Controller", step_size=step_size)
            controller_entity = controller_sim.Controller(controller=controller)
            world.connect(grid_entity, controller_entity, "p_delta")
            for actor_name, actor_entity in actor_names_and_entities:
                world.connect(actor_entity, controller_entity, ("p", f"actor.{actor_name}.p"))
                world.connect(actor_entity, controller_entity, ("info", f"actor.{actor_name}.info"))

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
        "Grid": {"python": "vessim.cosim.grid:GridSim"},
    }

    def __init__(self, sim_start):
        self.clock = Clock(sim_start)
        self.microgrids = []
        self.grid_signals = {}
        self.world = mosaik.World(self.COSIM_CONFIG)

    def add_microgrid(self, microgrid: Microgrid):
        self.microgrids.append(microgrid)

    def add_grid_signal(self, name: str, grid_signal: Signal):
        if len(self.microgrids) > 0:
            raise RuntimeError("Add all grid signals before adding microgrids.")
        self.grid_signals[name] = grid_signal

    def run(
        self,
        until: Optional[int] = None,
        rt_factor: Optional[float] = None,
        print_progress: Union[bool, Literal["individual"]] = True,
    ):
        try:
            for microgrid in self.microgrids:
                microgrid.initialize(self.world, self.clock, self.grid_signals)
            if until is None:
                until = int("inf")
            self.world.run(until=until, rt_factor=rt_factor, print_progress=print_progress)
        except Exception as e:
            if str(e).startswith("Simulation too slow for real-time factor"):
                return
            for microgrid in self.microgrids:
                microgrid.finalize()
            raise
