import mosaik

from vessim import TimeSeriesApi
from vessim.core.microgrid import Microgrid


class Environment:
    COSIM_CONFIG = {
        "Actor": {
            "python": "vessim.cosim.actor:ActorSim",
        },
        "Ecovisor": {
            "python": "vessim.cosim.ecovisor:EcovisorSim",
        },
        "Grid": {
            "python": "vessim.cosim.grid:GridSim"
        },
    }

    def __init__(self, sim_start):
        self.sim_start = sim_start
        self.microgrids = []
        self.grid_signals = {}
        self.world = mosaik.World(self.COSIM_CONFIG)

    def add_microgrid(self, microgrid: Microgrid):
        microgrid.initialize(self.world, self.sim_start, self.grid_signals)
        self.microgrids.append(microgrid)

    def add_grid_signal(self, name: str, grid_signal: TimeSeriesApi):
        if len(self.microgrids) > 0:
            raise RuntimeError("Add all grid signals before adding microgrids.")
        self.grid_signals[name] = grid_signal

    def run(self, until):
        self.world.run(until=until)
