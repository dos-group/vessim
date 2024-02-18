from _data import load_solar_data
from vessim.actor import ComputingSystem, Generator
from vessim.controller import Monitor
from vessim.cosim import Environment
from vessim.power_meter import MockPowerMeter
from vessim.signal import HistoricalSignal
from vessim.storage import SimpleBattery

SIM_START = "2020-06-11 00:00:00"
DURATION = 3600 * 24 * 2  # two days


def main(result_csv: str):
    environment = Environment(sim_start=SIM_START)

    monitor = Monitor()  # stores simulation result on each step
    environment.add_microgrid(
        actors=[
            ComputingSystem(power_meters=[
                MockPowerMeter(p=2.194),
                MockPowerMeter(p=7.6)
            ]),
            Generator(signal=HistoricalSignal(load_solar_data(sqm=0.4 * 0.5))),
        ],
        controllers=[monitor],
        storage=SimpleBattery(capacity=100),
        step_size=60,  # global step size (can be overridden by actors or controllers)
    )

    environment.run(until=DURATION)
    monitor.to_csv(result_csv)


if __name__ == "__main__":
    main(result_csv="result.csv")
