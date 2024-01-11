from vessim.core import TimeSeriesApi
from vessim.cosim import Microgrid, Environment, ComputingSystem, Generator, Monitor, \
    MockPowerMeter, SimpleBattery

SIM_START = "2020-06-11 00:00:00"
DURATION = 3600 * 24 * 2  # two days
STORAGE = SimpleBattery(
    capacity=32 * 5 * 3600,  # 10Ah * 5V * 3600 := Ws
    charge_level=32 * 5 * 3600 * .6,
    min_soc=.6
)
SOLAR_DATASET = {"actual": "solar_berlin_2021-06.csv", "fill_method": "ffill"}
CARBON_DATASET = {"actual": "carbon_intensity.csv", "fill_method": "ffill"}


def main(result_csv: str):
    environment = Environment(sim_start=SIM_START)

    solar_api = TimeSeriesApi.from_dataset(
        SOLAR_DATASET,
        "./data",
        scale=0.4 * 0.5 * .17,
        start_time="2020-06-01 00:00:00",
        use_forecast=False,
    )

    carbon_api = TimeSeriesApi.from_dataset(CARBON_DATASET, "./data", use_forecast=False)

    environment.add_grid_signal("carbon_intensity", carbon_api)

    monitor = Monitor(step_size=60)
    microgrid = Microgrid(
        actors=[
            ComputingSystem(
                name="server",
                step_size=60,
                power_meters=[
                    MockPowerMeter(name="mpm0", p=2.194),
                    MockPowerMeter(name="mpm1", p=7.6)
                ]
            ),
            Generator(name="solar", step_size=60, time_series_api=solar_api),
        ],
        controllers=[monitor],
        storage=STORAGE,
        zone="DE",
    )

    environment.add_microgrid(microgrid)
    environment.run(until=DURATION)
    monitor.monitor_log_to_csv(result_csv)


if __name__ == "__main__":
    main(result_csv="result.csv")
