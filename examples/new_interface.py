from examples._data import load_solar_data
from vessim import TimeSeriesApi
from vessim.core.actor import ComputingSystem, Generator, MockPowerMeter
from vessim.core.enviroment import Environment
from vessim.core.microgrid import Microgrid
from vessim.core.storage import SimpleBattery


SIM_START = "2020-06-11 00:00:00"
DURATION = 3600 * 24 * 2  # two days
STORAGE = SimpleBattery(capacity=32 * 5 * 3600,  # 10Ah * 5V * 3600 := Ws
                        charge_level=32 * 5 * 3600 * .6,
                        min_soc=.6)


def main():
    environment = Environment(sim_start=SIM_START)

    microgrid = Microgrid(
        actors=[
            ComputingSystem(
                name="server",
                power_meters=[
                    MockPowerMeter(name="mpm0", p=2.194),
                    MockPowerMeter(name="mpm1", p=7.6)
                ]
            ),
            Generator(
                name="solar",
                time_series_api=TimeSeriesApi(load_solar_data(sqm=0.4 * 0.5))
            ),
        ],
        storage=STORAGE,
        # grid_signals=...,
    )

    environment.add(microgrid)
    environment.run(until=DURATION)

    microgrid.ecovisor.monitor_to_csv("result.csv")


if __name__ == "__main__":
    main()
