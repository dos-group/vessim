"""1st example scenario.

As described in 'Software-in-the-loop simulation for developing and testing carbon-aware
applications'.
"""
from datetime import timedelta

import mosaik
import pandas as pd

from simulator.power_meter import MockPowerMeter
from vessim.carbon_api import CarbonApi
from vessim.storage import SimpleBattery, DefaultStoragePolicy

sim_config = {
    "CSV": {
        "python": "mosaik_csv:CSV",
    },
    "Microgrid": {
        "python": "vessim.microgrid:MicrogridSim"
    },
    "ComputingSystem": {
        "python": "simulator.computing_system:ComputingSystemSim",
    },
    "Monitor": {
        "python": "vessim.monitor:Monitor",
    },
    "SolarController": {
        "python": "simulator.solar_controller:SolarController",
    },
    "CarbonApi": {
        "python": "vessim.carbon_api:CarbonApiSim",
    },
}


def main(sim_start: str,
         duration: int,
         carbon_data_file: str,
         solar_data_file: str,
         battery_capacity: float,
         battery_initial_soc: float,
         battery_min_soc: float,
         battery_c_rate: float):
    """Execute the example scenario simulation."""
    world = mosaik.World(sim_config)

    power_meter = MockPowerMeter(return_value=50)
    computing_system_sim = world.start('ComputingSystem', step_size=60)
    computing_system = computing_system_sim.ComputingSystemModel(
        power_meters=[power_meter],
        pue=1.5
    )

    # Carbon Intensity API
    data = pd.read_csv(carbon_data_file, index_col="Time", parse_dates=True)
    data.index -= timedelta(days=365 * 6)
    carbon_api_sim = world.start("CarbonApi", sim_start=sim_start,
                                 carbon_api=CarbonApi(data=data))
    carbon_api_de = carbon_api_sim.CarbonApi.create(1, zone="DE")[0]

    # Solar Sim from CSV dataset
    solar_sim = world.start("CSV", sim_start=sim_start, datafile=solar_data_file)
    solar = solar_sim.PV.create(1)[0]

    # Solar Controller acts as medium between solar module and VES or consumer,
    # as the producer only generates CSV data.
    solar_controller = world.start("SolarController")
    solar_agent = solar_controller.SolarAgent()

    ## Solar -> SolarAgent
    world.connect(solar, solar_agent, ("P", "solar"))

    microgrid_sim = world.start("Microgrid")
    battery = SimpleBattery(
        capacity=battery_capacity,
        charge_level=battery_capacity * battery_initial_soc,
        min_soc=battery_min_soc,
        c_rate=battery_c_rate,
    )
    policy = DefaultStoragePolicy()
    microgrid = microgrid_sim.MicrogridModel.create(1, storage=battery, policy=policy)[0]

    world.connect(solar_agent, microgrid, ("solar", "p_gen"))
    world.connect(computing_system, microgrid, ('p_cons', 'p_cons'))

    def monitor_fn():
        return {
            "battery_soc": battery.soc(),
            "battery_min_soc": battery.min_soc
        }

    # Monitor
    monitor_sim = world.start("Monitor")
    monitor = monitor_sim.Monitor(fn=monitor_fn, sim_start=sim_start)
    world.connect(microgrid, monitor, "p_gen", "p_cons", "p_grid")
    world.connect(carbon_api_de, monitor, "carbon_intensity")

    world.run(until=duration)


if __name__ == "__main__":
    main(
        sim_start="2014-01-01 00:00:00",
        duration=3600 * 12,
        carbon_data_file="data/carbon_intensity.csv",
        solar_data_file="data/pv_10kw.csv",
        battery_capacity=10 * 5 * 3600,  # 10Ah * 5V * 3600 := Ws
        battery_initial_soc=.7,
        battery_min_soc=.6,
        battery_c_rate=1,
    )
