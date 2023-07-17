"""Co-simulation example with software-in-the-loop.

This scenario builds on `cosim_example.py` but connects to a real computing system
through software-in-the-loop integration as described in our paper:
- 'Software-in-the-loop simulation for developing and testing carbon-aware applications'.
  [under review]

This is example experimental and documentation is still in progress.
"""

import mosaik  # type: ignore
import json
import subprocess
from vessim.cosim._util import disable_mosaik_warnings

from examples._data import load_carbon_data, load_solar_data
from examples.cosim_example import COSIM_CONFIG, SIM_START, STORAGE, DURATION
from vessim.core.microgrid import SimpleMicrogrid
from vessim.core.simulator import Generator, CarbonApi
from vessim.sil.node import Node
from vessim.sil.power_meter import HttpPowerMeter

COSIM_SIL_CACU_CONFIG = {
    **COSIM_CONFIG,
    "SilInterface": {
        "python": "vessim.cosim:SilInterfaceSim",
    },
}
GCP_ADDRESS = "http://35.198.148.144"
RASPI_ADDRESS = "http://192.168.207.71"

disable_mosaik_warnings()

def run_simulation():
    world = mosaik.World(COSIM_SIL_CACU_CONFIG)

    # Initialize nodes
    nodes=[
        Node(address=GCP_ADDRESS, name="gcp"),
        #Node(address=RASPI_ADDRESS, name="raspi")
    ]

    # Initialize computing system
    computing_system_sim = world.start('ComputingSystem', step_size=60)
    computing_system = computing_system_sim.ComputingSystem(
        power_meters=[
            HttpPowerMeter(interval=1, server_address=GCP_ADDRESS),
            #HttpPowerMeter(interval=1, server_address=RASPI_ADDRESS)
        ])

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

    # Software-in-the-loop integration
    sil_interface_sim = world.start("SilInterface", step_size=60)
    sil_interface = sil_interface_sim.SilInterface(
        nodes=nodes, storage=STORAGE, collection_interval=1/60, api_host="0.0.0.0"
    )
    world.connect(computing_system, sil_interface, ("p", "p_cons"))
    world.connect(solar, sil_interface, ("p", "p_gen"))
    world.connect(carbon_api_de, sil_interface, ("carbon_intensity", "ci"))
    world.connect(microgrid, sil_interface, ("p_delta", "p_grid"))

    # Connect all simulation entities and the battery to the monitor
    monitor_sim = world.start("Monitor", sim_start=SIM_START, step_size=60)
    monitor = monitor_sim.Monitor(out_path="data.csv",
                                  fn=lambda: dict(battery_soc=STORAGE.soc(),
                                                  battery_min_soc=STORAGE.min_soc))
    world.connect(solar, monitor, ("p", "p_solar"))
    world.connect(computing_system, monitor, ("p", "p_computing_system"))
    world.connect(microgrid, monitor, ("p_delta", "p_grid"))
    world.connect(carbon_api_de, monitor, "carbon_intensity")

    # Start carbon-aware control unit
    json_nodes = json.dumps({node.name: node.id for node in nodes})
    com = [
        sys.executable,
        "examples/sil/carbon-aware_control_unit/main.py",
        "--nodes",
        json_nodes
    ]
    cacu = subprocess.Popen(
        com, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    world.run(until=DURATION, rt_factor=1/60)

    # Terminate carbon-aware control unit
    cacu.terminate()

if __name__ == "__main__":
    run_simulation()
