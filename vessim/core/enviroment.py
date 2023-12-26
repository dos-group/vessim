import mosaik

from vessim import TimeSeriesApi
from vessim.core.microgrid import Microgrid


class Environment:
    COSIM_CONFIG = {
        "Actor": {
            "python": "vessim.cosim:ActorSim",
        },
        "Ecovisor": {
            "python": "vessim.cosim:EcovisorSim",
        },
        "Grid": {
            "python": "vessim.cosim:GridSim"
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
        # grid_signal_sim = self.world.start("GridSignal", grid_signal=grid_signal, sim_start=self.sim_start)  # TODO maybe this should be refactored to be on entity level?
        self.grid_signals[name] = grid_signal  # grid_signal_sim.GridSignal()

    def run(self, until):
        self.world.run(until=until)
