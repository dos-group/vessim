from __future__ import annotations
from datetime import datetime, timedelta

from _data import load_carbon_data, load_solar_data
from basic_example import SIM_START, DURATION
from vessim import HistoricalSignal
from vessim.cosim import (
    ComputingSystem,
    Generator,
    Monitor,
    Storage,
    MockPowerMeter,
    StoragePolicy,
    Microgrid,
    Environment,
    SimpleBattery,
)


def main(result_csv: str):
    environment = Environment(sim_start=SIM_START)
    signal = HistoricalSignal(load_carbon_data())
    environment.add_grid_signal("carbon_intensity", signal)

    monitor = Monitor()  # stores simulation result on each step
    microgrid = Microgrid(
        actors=[
            ComputingSystem(power_meters=[MockPowerMeter(p=3), MockPowerMeter(p=7)]),
            Generator(signal=HistoricalSignal(load_solar_data(sqm=0.4 * 0.5))),
        ],
        controllers=[monitor],
        storage=SimpleBattery(capacity=100),
        storage_policy=AdaptiveStoragePolicy(signal),
        zone="DE",
        step_size=60,  # global step size (can be overridden by actors or controllers)
    )
    environment.add_microgrid(microgrid)

    environment.run(until=DURATION)
    monitor.to_csv(result_csv)


class AdaptiveStoragePolicy(StoragePolicy):
    """Policy that uses data on energy availability.

    Args:
        renewable_forecast_signal: A signal class instance that provides
            forecast data on renewable energy availability.
        threshold: A float value representing the threshold of forecast data to
            consider it sufficient for charging.
    """

    def __init__(self, forecast_signal: HistoricalSignal, threshold: float = 0.7):
        self.forecast_signal = forecast_signal
        self.threshold = threshold

    def apply(self, storage: Storage, p_delta: float, time_since_last_step: int) -> float:
        current_time = datetime.now()
        forecast_data = self.forecast_signal.forecast(
            start_time=current_time,
            end_time=current_time + timedelta(seconds=time_since_last_step),
        )

        # Decide if the storage should be charged or discharged based on forecast
        if forecast_data.mean() > self.threshold:
            charge_power = min(p_delta, storage.soc())
            return storage.update(power=charge_power, duration=time_since_last_step)
        else:
            # Forecast is bad - prepare to use stored energy
            discharge_power = -min(p_delta, storage.soc())
            return storage.update(power=discharge_power, duration=time_since_last_step)

    def state(self) -> dict:
        return {
            "forecast_signal": str(self.forecast_signal),
            "threshold": self.threshold,
        }


if __name__ == "__main__":
    main(result_csv="result.csv")
