from __future__ import annotations
from _data import load_carbon_data, load_solar_data
from basic_example import SIM_START, DURATION
from vessim import HistoricalSignal
from vessim.cosim import (
    ComputingSystem,
    Generator,
    Monitor,
    Controller,
    Microgrid,
    Environment,
    MockPowerMeter,
    SimpleBattery,
)


def main(result_csv: str):
    environment = Environment(sim_start=SIM_START)
    environment.add_grid_signal("carbon_intensity", HistoricalSignal(load_carbon_data()))

    power_meters: list = [
        MockPowerMeter(name="mpm0", p=3),
        MockPowerMeter(name="mpm1", p=7),
    ]
    monitor = Monitor()  # stores simulation result on each step
    power_meter_controller = PowerMeterController(power_meters=power_meters)
    microgrid = Microgrid(
        actors=[
            ComputingSystem(power_meters=power_meters),
            Generator(signal=HistoricalSignal(load_solar_data(sqm=0.4 * 0.5))),
        ],
        storage=SimpleBattery(capacity=1000, charge_level=500),
        controllers=[monitor, power_meter_controller],
        zone="DE",
        step_size=60,  # global step size (can be overridden by actors or controllers)
    )
    environment.add_microgrid(microgrid)

    environment.run(until=DURATION)
    monitor.to_csv(result_csv)


class PowerMeterController(Controller):
    def __init__(self, power_meters: list[MockPowerMeter]):
        super().__init__()
        self.power_meters = power_meters

    def step(self, time: int, p_delta: float, actors: dict):
        for power_meter in self.power_meters:
            pm = power_meter.measure()
            if p_delta < 0:
                if pm > 1:
                    power_meter.set_power(pm - 1)
            elif p_delta > 0:
                power_meter.set_power(pm + 1)


if __name__ == "__main__":
    main(result_csv="result.csv")
