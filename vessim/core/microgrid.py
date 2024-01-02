import pickle
from copy import copy
from typing import List, Optional, Dict

import mosaik

from vessim import TimeSeriesApi
from vessim.core.storage import Storage, StoragePolicy
from vessim.cosim.util import Clock
from vessim.cosim.actor import Actor
from vessim.cosim.controller import Controller


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
