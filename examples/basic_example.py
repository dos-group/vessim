from vessim import HistoricalSignal
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

    solar_signal = HistoricalSignal.from_dataset(
        SOLAR_DATASET,
        "./data",
        scale=0.4 * 0.5 * .17,
        start_time="2020-06-01 00:00:00"
    )

    carbon_signal = HistoricalSignal.from_dataset(CARBON_DATASET, "./data")

    environment.add_grid_signal("carbon_intensity", carbon_signal)

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
            Generator(name="solar", step_size=60, signal=solar_signal),
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
