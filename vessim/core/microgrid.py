from datetime import datetime
from typing import List, Optional, Dict

import mosaik

from vessim import TimeSeriesApi
from vessim.core.storage import Storage, StoragePolicy
from vessim.cosim.actor import Actor
from vessim.cosim.ecovisor import Ecovisor


class Microgrid:
    def __init__(
        self,
        actors: List[Actor],
        ecovisor: Ecovisor = None,
        storage: Optional[Storage] = None,
        storage_policy: Optional[StoragePolicy] = None,
        zone: Optional[str] = None,
    ):
        self.actors = actors
        self.ecovisor = ecovisor if ecovisor is not None else Ecovisor()
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
        self.ecovisor.start(sim_start, grid_signals, self.zone)
        self.ecovisor.add_custom_monitor_fn(lambda: dict(battery_soc=self.storage.soc()))  # TODO example, this should be user-defined
        ecovisor_sim = world.start("Ecovisor", step_size=60)  # TODO step_size
        ecovisor_entity = ecovisor_sim.EcovisorModel(ecovisor=self.ecovisor)

        grid_sim = world.start("Grid")
        grid_entity = grid_sim.GridModel(storage=self.storage, policy=self.storage_policy)
        world.connect(grid_entity, ecovisor_entity, "p_delta")

        for actor in self.actors:
            actor_sim = world.start("Actor", sim_start=sim_start, step_size=60)  # TODO step_size
            actor_entity = actor_sim.ActorModel(actor=actor)
            world.connect(actor_entity, grid_entity, "p")
            world.connect(actor_entity, ecovisor_entity, ("p", f"actor/{actor.name}/p"))
            world.connect(actor_entity, ecovisor_entity, ("info", f"actor/{actor.name}/info"))
