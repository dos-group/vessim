"""Example: Real-time simulation monitoring with InfluxDB and Grafana.

1. pip install vessim[monitor]
2. docker compose -f examples/grafana/docker-compose.yml up -d
3. python examples/grafana_example.py
4. Open Grafana at http://localhost:3001
"""
import multiprocessing

import numpy as np
import pandas as pd

import vessim as vs

influx_config = vs.InfluxConfig(
    url="http://127.0.0.1:8086",
    token="vessim-dev-token",
    org="vessim_org",
    bucket="vessim_bucket",
)


def make_wind_trace(seed: int = 42, base: float = 4.0, amplitude: float = 3.0,
                    noise_scale: float = 1.0, phase: float = 0.0) -> vs.Trace:
    """Generate a synthetic wind trace with configurable characteristics."""
    start, end = "2022-06-15 00:00:00", "2022-08-15 00:00:00"
    idx = pd.date_range(start=start, end=end, freq="5min")
    np.random.seed(seed)

    t = np.arange(len(idx))
    minutes_per_day = 24 * 60
    daily_cycle = amplitude * np.sin(2 * np.pi * (t % minutes_per_day) / minutes_per_day + phase)
    trend = 0.5 * np.sin(2 * np.pi * t / (len(idx) * 2))
    noise = np.random.normal(scale=noise_scale, size=len(idx))

    wind = np.clip(base + daily_cycle + trend + noise, 0, None)
    actual = pd.DataFrame({"wind": wind}, index=idx)
    actual.index.name = "timestamp"
    return vs.Trace(actual)


def main():
    env = vs.Environment(sim_start="2022-06-15", step_size=300)

    wind_trace_1 = make_wind_trace(seed=42, base=4.0, amplitude=3.0, noise_scale=1.0)
    wind_trace_2 = make_wind_trace(seed=123, base=5.5, amplitude=4.0, noise_scale=1.5,
                                   phase=np.pi / 4)

    env.add_microgrid(
        name="datacenter",
        coords=(52.5200, 13.4050),
        actors=[
            vs.Actor(name="server", signal=vs.StaticSignal(value=-2000), tag="load"),
            vs.Actor(
                name="solar_panel_1",
                signal=vs.Trace.load(
                    "solcast2022_global", column="Berlin", params={"scale": 8500},
                ),
                tag="solar",
                coords=(52.5210, 13.4060),
            ),
            vs.Actor(
                name="solar_panel_2",
                signal=vs.Trace.load(
                    "solcast2022_global", column="Berlin", params={"scale": 5000},
                ),
                tag="solar",
                coords=(52.5205, 13.4070),
            ),
            vs.Actor(
                name="wind_turbine_1",
                signal=wind_trace_1,
                tag="wind",
                coords=(52.5190, 13.4040),
            ),
            vs.Actor(
                name="wind_turbine_2",
                signal=wind_trace_2,
                tag="wind",
                coords=(52.5180, 13.4030),
            ),
        ],
        storage=vs.SimpleBattery(capacity=50000),
    )

    env.add_microgrid(
        name="office",
        coords=(48.1351, 11.5820),
        actors=[
            vs.Actor(name="office_load", signal=vs.StaticSignal(value=-1200), tag="load"),
            vs.Actor(
                name="solar_panel",
                signal=vs.Trace.load(
                    "solcast2022_global", column="Berlin", params={"scale": 5000},
                ),
                tag="solar",
                coords=(48.1360, 11.5830),
            ),
        ],
        storage=vs.SimpleBattery(capacity=20000),
    )

    env.add_microgrid(
        name="factory",
        coords=(50.1109, 8.6821),
        actors=[
            vs.Actor(name="factory_load", signal=vs.StaticSignal(value=-3000), tag="load"),
            vs.Actor(
                name="solar_panel",
                signal=vs.Trace.load(
                    "solcast2022_global", column="Berlin", params={"scale": 10000},
                ),
                tag="solar",
                coords=(50.1115, 8.6830),
            ),
        ],
        storage=vs.SimpleBattery(capacity=30000),
    )

    env.add_controller(vs.InfluxLogger(influx_config=influx_config, sim_id="sim_run_001"))
    env.add_controller(vs.CsvLogger(outfile="./results.csv"))

    # Run simulation for 20 days
    print("\nOpen Grafana dashboard: http://localhost:3001/d/vessim-simple/vessim-energy-dashboard")
    env.run(3600 * 24 * 20)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
