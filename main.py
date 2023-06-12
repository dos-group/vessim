"""1st example scenario.

As described in 'Software-in-the-loop simulation for developing and testing carbon-aware
applications'.
"""
import argparse
from datetime import timedelta

import mosaik
import pandas as pd

from simulator.power_meter import MockPowerMeter, HttpPowerMeter, PowerMeter
from vessim.carbon_api import CarbonApi
from vessim.core import Node
from vessim.generator import Generator
from vessim.storage import SimpleBattery, DefaultStoragePolicy, Storage, StoragePolicy

sim_config = {
    "Microgrid": {
        "python": "vessim.microgrid:MicrogridSim"
    },
    "ComputingSystem": {
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
        "python": "simulator.virtual_energy_system:VirtualEnergySystemSim",
    },
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--simulated', action='store_true')  # on/off flag
    args = parser.parse_args()

    if args.simulated:
        nodes = []
        power_meters = [MockPowerMeter(p=-50)]
    else:
        ip = "http://192.168.149.71"
        nodes = [Node(ip)]
        power_meters = [HttpPowerMeter(interval=3, server_address=ip)]

    battery = SimpleBattery(
        capacity=10 * 5 * 3600,  # 10Ah * 5V * 3600 := Ws
        charge_level=10 * 5 * 3600 * .7,
        min_soc=.6,
        c_rate=1,
    )
    policy = DefaultStoragePolicy()

    run_simulation(
        sim_start="2014-01-01 00:00:00",
        duration=3600 * 12,
        carbon_data_file="data/carbon_intensity.csv",
        solar_data_file="data/pv_10kw.csv",
        nodes=nodes,
        power_meters=power_meters,
        battery=battery,
        policy=policy,
    )


def run_simulation(sim_start: str,
                   duration: int,
                   carbon_data_file: str,
                   solar_data_file: str,
                   nodes: list[Node],
                   power_meters: list[PowerMeter],
                   battery: SimpleBattery,
                   policy: StoragePolicy):
    """Execute the example scenario simulation."""
    world = mosaik.World(sim_config)

    computing_system_sim = world.start('ComputingSystem', step_size=60)
    computing_system = computing_system_sim.ComputingSystem(power_meters=power_meters)

    # Solar generator
    data = pd.read_csv(solar_data_file, index_col="Date", parse_dates=True)["P"]
    solar_sim = world.start("Generator", sim_start=sim_start,
                            generator=Generator(data=data))
    solar = solar_sim.Generator.create(1)[0]

    # Carbon Intensity API
    data = pd.read_csv(carbon_data_file, index_col="Date", parse_dates=True)
    data.index -= timedelta(days=365 * 6)
    carbon_api_sim = world.start("CarbonApi", sim_start=sim_start,
                                 carbon_api=CarbonApi(data=data))
    carbon_api_de = carbon_api_sim.CarbonApi.create(1, zone="DE")[0]

    # Connect consumers and producers to microgrid
    microgrid_sim = world.start("Microgrid")
    microgrid = microgrid_sim.Microgrid.create(1, storage=battery, policy=policy)[0]
    world.connect(computing_system, microgrid, "p")
    world.connect(solar, microgrid, "p")

    # If real scenario, init and connect VES
    if nodes:
        virtual_energy_system_sim = world.start("VirtualEnergySystem", step_size=60)
        virtual_energy_system = virtual_energy_system_sim.VirtualEnergySystem(
            nodes=nodes,
            battery=battery
        )
        world.connect(computing_system, virtual_energy_system, ("p", "p_cons"))
        world.connect(solar, virtual_energy_system, ("p", "p_gen"))
        world.connect(carbon_api_de, virtual_energy_system, ("carbon_intensity", "ci"))
        world.connect(microgrid, virtual_energy_system, ("p_delta", "p_grid"))

    # Monitor
    def monitor_fn():
        return {
            "battery_soc": battery.soc(),
            "battery_min_soc": battery.min_soc
        }

    monitor_sim = world.start("Monitor")
    monitor = monitor_sim.Monitor(fn=monitor_fn, sim_start=sim_start)
    world.connect(solar, monitor, ("p", "p_solar"))
    world.connect(computing_system, monitor, ("p", "p_computing_system"))
    world.connect(microgrid, monitor, ("p_delta", "p_grid"))
    world.connect(carbon_api_de, monitor, "carbon_intensity")

    world.run(until=duration)


if __name__ == "__main__":
    main()
