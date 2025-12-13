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

    microgrid = env.add_microgrid(
        name="datacenter",
        actors=[
            vs.Actor(name="server", signal=vs.StaticSignal(value=-2000)),
            vs.Actor(
                #tag="solar"
                name="solar_panel",
                signal=vs.Trace.load(
                    "solcast2022_global",
                    column="Berlin",
                    params={"scale": 8500},
                ),  # 8.5 kW max (aus deinem Beispiel)
            ),
            vs.Actor(
                name="wind_turbine",
                signal=wind_trace,  # hier hängt der neue Wind-Trace
            ),
        ],
        storage=vs.SimpleBattery(capacity=50000),
    )

    monitor = vs.Monitor(
        [microgrid],
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
