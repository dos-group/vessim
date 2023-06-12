"""1st example scenario.

As described in 'Software-in-the-loop simulation for developing and testing carbon-aware
applications'.
"""
from datetime import timedelta

import mosaik
import pandas as pd

from simulator.power_meter import HttpPowerMeter
from vessim.carbon_api import CarbonApi
from vessim.generator import Generator
from vessim.storage import SimpleBattery
from vessim.core import Node


# Config file for parameters and settings specification.
sim_config = {
    "ComputingSystemSim": {
        "python": "vessim.computing_system:ComputingSystemSim",
    },
    "Generator": {
        "python": "vessim.generator:GeneratorSim",
    },
    "CarbonApi": {
        "python": "vessim.carbon_api:CarbonApiSim",
    },
    "Monitor": {
        "python": "vessim.monitor:MonitorSim",
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

    gcp_node = Node("http://35.242.197.234")
    gcp_node.power_meter = HttpPowerMeter(
        interval=3,
        server_address=gcp_node.address,
        name="gcp_power_meter"
    )
    computing_system_sim = world.start('ComputingSystemSim')
    computing_system_sim.ComputingSystem(power_meters=[gcp_node.power_meter])

    # Carbon Intensity API
    data = pd.read_csv(carbon_data_file, index_col="Time", parse_dates=True)
    data.index -= timedelta(days=365 * 6)
    carbon_api_sim = world.start("CarbonApi", sim_start=sim_start,
                                 carbon_api=CarbonApi(data=data))
    carbon_api_de = carbon_api_sim.CarbonApi.create(1, zone="DE")[0]

    # Solar generator
    data = pd.read_csv(solar_data_file, index_col="Date", parse_dates=True)["P"]
    solar_sim = world.start("Generator", sim_start=sim_start,
                            generator=Generator(data=data))
    solar = solar_sim.Generator.create(1)[0]

    # VES Sim & Battery Sim
    battery = SimpleBattery(
        capacity=battery_capacity,
        charge_level=battery_capacity * battery_initial_soc,
        min_soc=battery_min_soc,
        c_rate=battery_c_rate,
    )
    virtual_energy_system_sim = world.start("VirtualEnergySystem")
    virtual_energy_system = virtual_energy_system_sim.VirtualEnergySystem(
        nodes=[gcp_node],
        battery=battery
    )

    collector = world.start("Monitor")
    monitor = collector.Monitor()

    ## Carbon -> VES
    world.connect(carbon_api_de, virtual_energy_system, ("carbon_intensity", "ci"))

    ## Solar -> VES
    world.connect(solar, virtual_energy_system, ("p", "solar"))

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
