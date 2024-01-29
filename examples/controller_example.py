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
    load_balancer = SimpleLoadBalancingController(
        max_load_adjustment=2, power_meters=power_meters
    )
    microgrid = Microgrid(
        actors=[
            ComputingSystem(power_meters=power_meters),
            Generator(signal=HistoricalSignal(load_solar_data(sqm=0.4 * 0.5))),
        ],
        storage=SimpleBattery(capacity=1000, charge_level=500),
        controllers=[monitor, load_balancer],
        zone="DE",
        step_size=60,  # global step size (can be overridden by actors or controllers)
    )
    environment.add_microgrid(microgrid)

    environment.run(until=DURATION)
    monitor.to_csv(result_csv)


class SimpleLoadBalancingController(Controller):
    def __init__(self, max_load_adjustment: float, power_meters: list[MockPowerMeter]):
        super().__init__()
        # The maximum load that can be adjusted at each step
        self.max_load_adjustment = max_load_adjustment
        self.power_meters = power_meters

    def step(self, time: int, p_delta: float, actors: dict) -> None:
        # Calculate the maximum adjustment per MockPowerMeter
        adjustment_per_meter = min(abs(p_delta), self.max_load_adjustment) / len(
            self.power_meters
        )

        # Adjust the power setpoint for each MockPowerMeter
        for power_meter in self.power_meters:
            current_power = power_meter.measure()
            # Determine direction of adjustment
            if p_delta < 0:
                new_power = current_power + adjustment_per_meter
            else:
                new_power = max(0, current_power - adjustment_per_meter)
            power_meter.set_power(new_power)


if __name__ == "__main__":
    main(result_csv="result.csv")
