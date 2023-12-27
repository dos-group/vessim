from datetime import datetime
from typing import List, Optional, Dict

import mosaik

from vessim import TimeSeriesApi
from vessim.core.storage import Storage, StoragePolicy
from vessim.cosim.actor import Actor
from vessim.cosim.controller import Controller


class Microgrid:
    def __init__(
        self,
        actors: List[Actor],
        controller: Controller,
        storage: Optional[Storage] = None,
        storage_policy: Optional[StoragePolicy] = None,
        zone: Optional[str] = None,
    ):
        self.actors = actors
        self.controller = controller
        self.storage = storage
        self.storage_policy = storage_policy
        self.zone = zone

    def initialize(
        self,
        world: mosaik.World,
        sim_start: datetime,
        grid_signals: Dict[str, TimeSeriesApi]
    ):
        """Create co-simulation entities and connect them to world"""
        self.controller.start(self, sim_start, grid_signals)
        controller_sim = world.start("Controller", step_size=self.controller.step_size)
        controller_entity = controller_sim.ControllerModel(controller=self.controller)

        grid_sim = world.start("Grid")
        grid_entity = grid_sim.Grid(storage=self.storage, policy=self.storage_policy)
        world.connect(grid_entity, controller_entity, "p_delta")

        for actor in self.actors:
            actor_sim = world.start("Actor", sim_start=sim_start, step_size=actor.step_size)
            actor_entity = actor_sim.ActorModel(actor=actor)
            world.connect(actor_entity, grid_entity, "p")
            world.connect(actor_entity, controller_entity, ("p", f"actor/{actor.name}/p"))
            world.connect(actor_entity, controller_entity, ("info", f"actor/{actor.name}/info"))
