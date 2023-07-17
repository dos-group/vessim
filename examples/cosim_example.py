"""Co-simulation example.

Runs a fully simulated example scenario over the course of two days.
"""

import mosaik  # type: ignore

from examples._data import load_carbon_data, load_solar_data
from vessim.core.microgrid import SimpleMicrogrid
from vessim.core.simulator import Generator, CarbonApi
from vessim.core.storage import SimpleBattery
from vessim.sil.power_meter import MockPowerMeter  # TODO PowerMeter should not be in sil
from vessim.cosim._util import disable_mosaik_warnings

COSIM_CONFIG = {
    "Microgrid": {
        "python": "vessim.cosim:MicrogridSim"
    },
    "ComputingSystem": {
        "python": "vessim.cosim:ComputingSystemSim",
    },
    "Generator": {
        "python": "vessim.cosim:GeneratorSim",
    },
    "CarbonApi": {
        "python": "vessim.cosim:CarbonApiSim",
    },
    "Monitor": {
        "python": "vessim.cosim:MonitorSim",
    }
}
SIM_START = "2020-06-11 00:00:00"
DURATION = 3600 * 24 * 2  # two days
STORAGE = SimpleBattery(capacity=10 * 5 * 3600,  # 10Ah * 5V * 3600 := Ws
                        charge_level=10 * 5 * 3600 * .6,
                        min_soc=.6,
                        c_rate=1)

disable_mosaik_warnings()

def run_simulation():
    world = mosaik.World(COSIM_CONFIG)

    # Initialize computing system
    computing_system_sim = world.start('ComputingSystem', step_size=60)
    computing_system = computing_system_sim.ComputingSystem(
        power_meters=[MockPowerMeter(p=10)])

    # Initialize solar generator
    solar_sim = world.start("Generator", sim_start=SIM_START)
    solar = solar_sim.Generator(generator=Generator(data=load_solar_data(sqm=0.4 * 0.5)))

    # Initialize carbon intensity API
    carbon_api_sim = world.start("CarbonApi", sim_start=SIM_START,
                                 carbon_api=CarbonApi(data=load_carbon_data()))
    carbon_api_de = carbon_api_sim.CarbonApi(zone="DE")

    # Connect consumers and producers to microgrid
    microgrid_sim = world.start("Microgrid")
    microgrid = microgrid_sim.Microgrid(microgrid=SimpleMicrogrid(storage=STORAGE))
    world.connect(computing_system, microgrid, "p")
    world.connect(solar, microgrid, "p")

    # Connect all simulation entities and the battery to the monitor
    monitor_sim = world.start("Monitor", sim_start=SIM_START, step_size=60)
    monitor = monitor_sim.Monitor(out_path="data.csv",
                                  fn=lambda: dict(battery_soc=STORAGE.soc(),
                                                  battery_min_soc=STORAGE.min_soc))
    world.connect(solar, monitor, ("p", "p_solar"))
    world.connect(computing_system, monitor, ("p", "p_computing_system"))
    world.connect(microgrid, monitor, ("p_delta", "p_grid"))
    world.connect(carbon_api_de, monitor, "carbon_intensity")

    world.run(until=DURATION)


if __name__ == "__main__":
    run_simulation()
