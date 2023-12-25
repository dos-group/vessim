from typing import List, Optional

from vessim.core.actor import Actor
from vessim.core.storage import Storage, StoragePolicy


class Microgrid:
    def __init__(
        self,
        actors: List[Actor],
        storage: Optional[Storage] = None,
        storage_policy: Optional[StoragePolicy] = None,
        # grid_signals: Optional[Dict[str, TimeSeriesApi]] = None,
        # ecovisor: Optional[Ecovisor] = None,
        # monitor: bool = False,
    ):
        self.actors = actors
        self.storage = storage
        self.storage_policy = storage_policy
        # self.grid_signals = grid_signals
        # self.ecovisor = ecovisor
        # self.monitor = monitor

    def initialize(self, world, sim_start):
        """Create co-simulation entities and connect them to world"""
        grid_sim = world.start("Grid")
        grid = grid_sim.Grid(storage=self.storage, policy=self.storage_policy)

        for actor in self.actors:
            actor_sim = world.start("Actor", sim_start=sim_start, step_size=60)  # TODO step_size, probably it should be an actor property? or maybe we should get this argument out of ActorSim
            actor_sim_entity = actor_sim.Actor(actor=actor)
            world.connect(actor_sim_entity, grid, "p")
