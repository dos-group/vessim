"""1st example scenario.

As described in 'Software-in-the-loop simulation for developing and testing carbon-aware
applications'.
"""
from datetime import timedelta

import mosaik
import pandas as pd

from simulator.power_meter import HttpPowerMeter
from vessim.carbon_api import CarbonApi
from vessim.storage import SimpleBattery


# Config file for parameters and settings specification.
sim_config = {
    "CSV": {
        "python": "mosaik_csv:CSV",
    },
    "ComputingSystemSim": {
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
    "VirtualEnergySystem": {
        "python": "simulator.virtual_energy_system:VirtualEnergySystem",
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

    gcp_power_meter = HttpPowerMeter("http://35.242.197.234", name="gcp_power_meter")
    computing_system_sim = world.start('ComputingSystemSim')
    computing_system_sim.ComputingSystem(power_meters=[gcp_power_meter])

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

    # VES Sim & Battery Sim
    battery = SimpleBattery(
        capacity=battery_capacity,
        charge_level=battery_capacity * battery_initial_soc,
        min_soc=battery_min_soc,
        c_rate=battery_c_rate,
    )
    virtual_energy_system_sim = world.start("VirtualEnergySystem")
    virtual_energy_system = virtual_energy_system_sim.VirtualEnergySystemModel(
        battery=battery
    )

    collector = world.start("Monitor")
    monitor = collector.Monitor()

    # Connect entities
    # world.connect(computing_system, monitor, 'p_cons')

    ## Carbon -> VES
    world.connect(carbon_api_de, virtual_energy_system, ("carbon_intensity", "ci"))

    ## Solar -> SolarAgent -> VES
    world.connect(solar, solar_agent, ("P", "solar"))
    world.connect(solar_agent, virtual_energy_system, "solar")

    ## computing_system -> VES
    # world.connect(
    #   computing_system, virtual_energy_system, (
    #       'p_con', 'consumption'
    #   )
    # )

    world.connect(
        virtual_energy_system,
        monitor,
        "consumption",
        "battery_min_soc",
        "battery_soc",
        "solar",
        "ci",
    )

    world.run(until=duration, print_progress=False, rt_factor=1)


if __name__ == "__main__":
    main(
        sim_start="2014-01-01 00:00:00",
        duration=300,
        carbon_data_file="data/carbon_intensity.csv",
        solar_data_file="data/pv_10kw.csv",
        battery_capacity=10 * 5 * 3600,  # 10Ah * 5V * 3600 := Ws
        battery_initial_soc=.7,
        battery_min_soc=.6,
        battery_c_rate=.2,
    )
