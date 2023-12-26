import mosaik

from vessim.core.microgrid import Microgrid


class Environment:
    COSIM_CONFIG = {
        "Grid": {
            "python": "vessim.cosim:GridSim"
        },
        "Actor": {
            "python": "vessim.cosim:ActorSim",
        },
        "Ecovisor": {
            "python": "vessim.cosim:EcovisorSim",
        },
        # TODO implement grid level signals
        # "CarbonApi": {
        #     "python": "vessim.cosim:CarbonApiSim",
        # },
    }

    def __init__(self, sim_start):
        self.sim_start = sim_start
        self.microgrids = []
        self.world = mosaik.World(self.COSIM_CONFIG)

    def add(self, microgrid: Microgrid):
        microgrid.initialize(self.world, self.sim_start)
        self.microgrids.append(microgrid)

    def run(self, until):
        self.world.run(until=until)
