"""Example scenario.

Runs a fully simulated example scenario over the course of two days.

If run with `--sil`, the scenario is executed with full software-in-the-loop integration
as described in 'Software-in-the-loop simulation for developing and testing carbon-aware
applications'. Documentation for this is in progress.
"""
import argparse
from datetime import timedelta
from typing import List, Union

import mosaik # type: ignore
import pandas as pd

from vessim.core.microgrid import SimpleMicrogrid
from vessim.core.simulator import Generator, CarbonApi
from vessim.core.storage import SimpleBattery, DefaultStoragePolicy, StoragePolicy
from vessim.sil.node import Node
from vessim.sil.power_meter import MockPowerMeter, HttpPowerMeter, PowerMeter

sim_config = {
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
    },
    "SilInterface": {
        "python": "vessim.cosim:SilInterfaceSim",
    },
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--sil', action='store_true')  # on/off flag
    args = parser.parse_args()

    if args.sil:
        #rpi_ip = "http://192.168.149.71"
        gcp_ip = "http://34.159.124.254"
        nodes = [Node(gcp_ip)]#, Node(rpi_ip)]
        power_meters = [
            HttpPowerMeter(interval=1, server_address=gcp_ip)
        ]
    else:
        nodes = []
        power_meters = [MockPowerMeter(p=10)]

    battery = SimpleBattery(
        capacity=10 * 5 * 3600,  # 10Ah * 5V * 3600 := Ws
        charge_level=10 * 5 * 3600 * .6,
        min_soc=.6,
        c_rate=1,
    )
    policy = DefaultStoragePolicy()

    run_simulation(
        sim_start="2020-06-11 00:00:00",
        duration=3600 * 24 * 2,  # two days
        carbon_data_file="data/carbon_intensity.csv",
        solar_data_file="data/weather_berlin_2021-06.csv",
        nodes=nodes,
        power_meters=power_meters,
        battery=battery,
        policy=policy,
    )


def run_simulation(sim_start: str,
                   duration: int,
                   carbon_data_file: str,
                   solar_data_file: str,
                   nodes: List[Node],
                   power_meters: List[PowerMeter],
                   battery: SimpleBattery,
                   policy: StoragePolicy):
    """Execute the example scenario simulation."""
    world = mosaik.World(sim_config)

    computing_system_sim = world.start('ComputingSystem', step_size=60)
    computing_system = computing_system_sim.ComputingSystem(power_meters=power_meters)

    # Solar generator (scaling solar data for scenario)
    data : Union[pd.DataFrame, pd.Series] = pd.read_csv(
        solar_data_file,
        index_col="time",
        parse_dates=True)["solar"] * 0.4 * 0.5 * .17  # W/m^2 * m^2 = W
    data.index -= timedelta(days=365)
    data = data.astype(float)
    solar_sim = world.start("Generator", sim_start=sim_start,
                            generator=Generator(data=data))
    solar = solar_sim.Generator.create(1)[0]

    # Carbon Intensity API
    data = pd.read_csv(carbon_data_file, index_col="time", parse_dates=True)
    carbon_api_sim = world.start("CarbonApi", sim_start=sim_start,
                                 carbon_api=CarbonApi(data=data))
    carbon_api_de = carbon_api_sim.CarbonApi.create(1, zone="DE")[0]

    # Connect consumers and producers to microgrid
    microgrid_sim = world.start("Microgrid")
    microgrid = microgrid_sim.Microgrid(
        microgrid=SimpleMicrogrid(storage=battery, policy=policy)
    )
    world.connect(computing_system, microgrid, "p")
    world.connect(solar, microgrid, "p")

    # If real scenario, init and connect VES
    if nodes:
        sil_interface_sim = world.start("SilInterface", step_size=60)
        sil_interface = sil_interface_sim.SilInterface(
            nodes=nodes,
            battery=battery,
            policy=policy,
            collection_interval=1
        )
        world.connect(computing_system, sil_interface, ("p", "p_cons"))
        world.connect(solar, sil_interface, ("p", "p_gen"))
        world.connect(carbon_api_de, sil_interface, ("carbon_intensity", "ci"))
        world.connect(microgrid, sil_interface, ("p_delta", "p_grid"))

    # Monitor
    def monitor_fn():
        return {
            "battery_soc": battery.soc(),
            "battery_min_soc": battery.min_soc
        }

    monitor_sim = world.start("Monitor", sim_start=sim_start, step_size=60)
    monitor = monitor_sim.Monitor(out_path="data.csv", fn=monitor_fn)
    world.connect(solar, monitor, ("p", "p_solar"))
    world.connect(computing_system, monitor, ("p", "p_computing_system"))
    world.connect(microgrid, monitor, ("p_delta", "p_grid"))
    world.connect(carbon_api_de, monitor, "carbon_intensity")

    world.run(until=duration)#, rt_factor=1/60)


if __name__ == "__main__":
    main()
