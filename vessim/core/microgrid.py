from typing import List, Optional

from vessim.core.actor import Actor
from vessim.core.storage import Storage, StoragePolicy
from vessim.cosim.ecovisor import Ecovisor


class Microgrid:
    def __init__(
        self,
        actors: List[Actor],
        ecovisor: Ecovisor = None,
        storage: Optional[Storage] = None,
        storage_policy: Optional[StoragePolicy] = None,
        # TODO in the future we want to support multiple simultaneous grid signals like
        #  carbon intensity, price, average carbon intensity, ...
        # grid_signal: Optional[TimeSeriesApi] = None,
    ):
        self.actors = actors
        if ecovisor is None:
            self.ecovisor = Ecovisor(monitor_fn=lambda: dict(battery_soc=storage.soc()))
        else:
            self.ecovisor = ecovisor

        self.storage = storage
        self.storage_policy = storage_policy
        # self.grid_signal = grid_signal

    def initialize(self, world, sim_start):
        """Create co-simulation entities and connect them to world"""
        self.ecovisor.initialize(sim_start)
        ecovisor_sim = world.start("Ecovisor", step_size=60)  # TODO step_size
        ecovisor_entity = ecovisor_sim.Ecovisor(ecovisor=self.ecovisor)

        grid_sim = world.start("Grid")
        grid_entity = grid_sim.Grid(storage=self.storage, policy=self.storage_policy)
        world.connect(grid_entity, ecovisor_entity, "p_delta")

        for actor in self.actors:
            actor_sim = world.start("Actor", sim_start=sim_start, step_size=60)  # TODO step_size
            actor_entity = actor_sim.Actor(actor=actor)
            world.connect(actor_entity, grid_entity, "p")
            world.connect(actor_entity, ecovisor_entity, ("p", f"{actor.name}/p"))
