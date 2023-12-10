"""Co-simulation example.

Runs a fully simulated example scenario over the course of two days.
"""
import argparse

from _data import load_carbon_data, load_solar_data
from vessim import TimeSeriesApi
from vessim.core.consumer import ComputingSystem, MockPowerMeter
from vessim.core.microgrid import SimpleMicrogrid
from vessim.core.storage import SimpleBattery, DefaultStoragePolicy
from vessim.cosim._util import VessimCoordinator
from vessim.cosim import (
    CarbonApi,
    Consumer,
    Generator,
    Microgrid,
    Monitor
)
from util.simulated_cacu import Cacu


SIM_START = "2020-06-11 00:00:00"
DURATION = 3600 * 24 * 2  # two days
STORAGE = SimpleBattery(capacity=32 * 5 * 3600,  # 10Ah * 5V * 3600 := Ws
                        charge_level=32 * 5 * 3600 * .6,
                        min_soc=.6)
STORAGE_POLICY = DefaultStoragePolicy()


def run_simulation(carbon_aware: bool, result_csv: str):
    coordinator = VessimCoordinator(SIM_START, DURATION, STORAGE, STORAGE_POLICY)

    # Initialize carbon API
    carbon_api_de = CarbonApi(TimeSeriesApi(actual=load_carbon_data()), "DE")
    coordinator.start_sim(carbon_api_de)

    # Initialize computing system with mock power meters
    mock_power_meters = [
        MockPowerMeter(name="mpm0", p=2.194),
        MockPowerMeter(name="mpm1", p=7.6)
    ]
    computing_system = Consumer(ComputingSystem(power_meters=mock_power_meters))
    coordinator.start_sim(computing_system)

    # Initialize solar generators
    solar = Generator(TimeSeriesApi(actual=load_solar_data(sqm=0.4 * 0.5)))
    coordinator.start_sim(solar)

    # Initialize simple microgrid
    microgrid = Microgrid(SimpleMicrogrid(storage=STORAGE, policy=STORAGE_POLICY))
    coordinator.start_sim(microgrid)

    # Initialize monitor
    monitor = Monitor(out_path=result_csv,
                      fn=lambda: dict(battery_soc=STORAGE.soc(),
                                      battery_min_soc=STORAGE.min_soc))
    coordinator.start_sim(monitor)

    if carbon_aware:
        # Initialize carbon-aware control unit
        cacu = Cacu(mock_power_meters, STORAGE, STORAGE_POLICY)
        coordinator.start_sim(cacu)
        # Connect ci to cacu
        coordinator.connect(carbon_api_de, cacu, ("carbon_intensity", "ci"))

    # Connect consumers and producers to microgrid
    coordinator.connect(computing_system, microgrid, "p")
    coordinator.connect(solar, microgrid, "p")
    coordinator.connect(solar, monitor, ("p", "p_solar"))

    # Connect all simulation entities and the battery to the monitor
    coordinator.connect(computing_system, monitor, ("p", "p_computing_system"))
    coordinator.connect(computing_system, monitor, ("info", "computing_system_info"))
    coordinator.connect(microgrid, monitor, ("p_delta", "p_grid"))
    coordinator.connect(carbon_api_de, monitor, "carbon_intensity")

    coordinator.run_cosim()



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--carbon_aware", action="store_true",
                        help="Run the experiment in a carbon-aware manner")
    parser.add_argument("--out", type=str, default="result.csv",
                        help="Path to output CSV file")
    args = parser.parse_args()
    run_simulation(carbon_aware=args.carbon_aware, result_csv=args.out)
