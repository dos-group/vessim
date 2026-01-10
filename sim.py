import multiprocessing
import vessim as vs
import csv
import requests
from datetime import datetime, timezone

import pandas as pd
import numpy as np

import os
from dotenv import load_dotenv

load_dotenv()

# UPDATED INFLUXDB 2 CONFIGURATION ---
INFLUX_URL = "http://127.0.0.1:8086"
INFLUX_ORG = "vessim_org"
INFLUX_BUCKET = "vessim_bucket"
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN")

# ---------------------------------------------------------
# Berlin-Winddaten als Trace (synthetisch, 5-Minuten-Raster)
# ---------------------------------------------------------
def make_berlin_wind_trace():
    start = "2022-06-15 00:00:00"
    end   = "2022-08-15 00:00:00"

    # 5-Minuten-Index, ohne Zeitzone (naive Timestamps wie im Trace-Beispiel)
    idx = pd.date_range(start=start, end=end, freq="5min")

    np.random.seed(42)

    # Tagesgang: Sinus über 24h
    minutes_per_day = 24 * 60
    t = np.arange(len(idx))
    daily_cycle = 3 * np.sin(2 * np.pi * (t % minutes_per_day) / minutes_per_day)

    # Langsamer Trend (z.B. leicht windiger im Verlauf)
    trend = 0.5 * np.sin(2 * np.pi * t / (len(idx) * 2))

    # Grundniveau + Rauschen
    base = 4.0
    noise = np.random.normal(scale=1.0, size=len(idx))

    wind = base + daily_cycle + trend + noise
    wind = np.clip(wind, 0, None)  # kein negativer Wind

    actual = pd.DataFrame(
        {
            "wind": wind,
        },
        index=idx,
    )
    actual.index.name = "timestamp"

    # Nur Actual reicht, Forecast brauchst du hier nicht zwingend
    return vs.Trace(actual)


def main():
    # 300s = 5 Minuten
    env = vs.Environment(sim_start="2022-06-15", step_size=300)

    # Wind-Trace erzeugen
    wind_trace = make_berlin_wind_trace()

    datacenter = env.add_microgrid(
        name="datacenter",
        coords=(52.5200, 13.4050),
        actors=[
            vs.Actor(name="server", signal=vs.StaticSignal(value=-2000), tag="load"),
            vs.Actor(
                name="solar_panel",
                signal=vs.Trace.load(
                    "solcast2022_global",
                    column="Berlin",
                    params={"scale": 8500},
                ),
                tag="solar",
                coords=(52.5210, 13.4060),  # Slightly offset from datacenter
            ),
            vs.Actor(
                name="wind_turbine",
                signal=wind_trace,
                tag="wind",
                coords=(52.5190, 13.4040),  # Slightly offset from datacenter
            ),
        ],
        storage=vs.SimpleBattery(capacity=50000),
    )

    office = env.add_microgrid(
        name="office",
        coords=(48.1351, 11.5820),
        actors=[
            vs.Actor(name="office_load", signal=vs.StaticSignal(value=-1200), tag="load"),
            vs.Actor(
                name="solar_panel",
                signal=vs.Trace.load(
                    "solcast2022_global",
                    column="Berlin",
                    params={"scale": 5000},
                ),
                tag="solar",
                coords=(48.1360, 11.5830),  # Slightly offset from office
            ),
        ],
        storage=vs.SimpleBattery(capacity=20000),
    )

    factory = env.add_microgrid(
        name="factory",
        coords=(50.1109, 8.6821),
        actors=[
            vs.Actor(name="factory_load", signal=vs.StaticSignal(value=-3000), tag="load"),
            vs.Actor(
                name="solar_panel",
                signal=vs.Trace.load(
                    "solcast2022_global",
                    column="Berlin",
                    params={"scale": 10000},
                ),
                tag="solar",
                coords=(50.1115, 8.6830),  # Slightly offset from factory
            ),
        ],
        storage=vs.SimpleBattery(capacity=30000),
    )

    # Monitor für beide Microgrids
    monitor = vs.Monitor(
        [datacenter, office, factory],  # <-- hier beide übergeben
        outfile="./results.csv",
        influx_url=INFLUX_URL,
        influx_org=INFLUX_ORG,
        influx_bucket=INFLUX_BUCKET,
        influx_token=INFLUX_TOKEN,
    )
    env.add_controller(monitor)

    # 20 Tage Simulation
    env.run(3600 * 24 * 20)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
