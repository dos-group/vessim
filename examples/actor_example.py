from __future__ import annotations
from datetime import datetime

from _data import load_carbon_data, load_solar_data
from basic_example import SIM_START, DURATION
from vessim import HistoricalSignal
from vessim.cosim import (
    Generator,
    Monitor,
    Actor,
    Microgrid,
    Environment,
    SimpleBattery,
)


def main(result_csv: str):
    environment = Environment(sim_start=SIM_START)
    environment.add_grid_signal("carbon_intensity", HistoricalSignal(load_carbon_data()))

    monitor = Monitor()  # stores simulation result on each step
    microgrid = Microgrid(
        actors=[
            Household(name="TEL 12", base_power=3),
            Generator(signal=HistoricalSignal(load_solar_data(sqm=0.4 * 0.5))),
        ],
        controllers=[monitor],
        storage=SimpleBattery(capacity=100),
        zone="DE",
        step_size=60,  # global step size (can be overridden by actors or controllers)
    )
    environment.add_microgrid(microgrid)

    environment.run(until=DURATION)
    monitor.to_csv(result_csv)


class Household(Actor):
    def __init__(self, name: str, base_power: float):
        super().__init__(name)
        self.base_power = base_power  # base power consumption

    def p(self, now: datetime) -> float:
        hour = now.hour
        # power consumption is higher during 6 PM to 10 PM (evening hours)
        if 18 <= hour < 22:
            return self.base_power * 1.5
        # power consumption is less during 12 AM to 6 AM (sleeping hours)
        elif 0 <= hour < 6:
            return self.base_power * 0.5
        else:
            return self.base_power


if __name__ == "__main__":
    main(result_csv="result.csv")
