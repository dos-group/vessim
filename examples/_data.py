from datetime import timedelta

import pandas as pd
import os

BASE_DIR = os.path.dirname(__file__)
SOLAR_DATA_FILE = f"{BASE_DIR}/data/weather_berlin_2021-06.csv"
CARBON_DATA_FILE = f"{BASE_DIR}/data/carbon_intensity.csv"


def load_solar_data(sqm: float) -> pd.Series:
    irradiance_data = pd.read_csv(SOLAR_DATA_FILE, index_col="time",
                                  parse_dates=True)["solar"]
    irradiance_data.index -= timedelta(days=365)
    production_data = irradiance_data * sqm * .17  # W/m^2 * m^2 = W
    return production_data.astype(float)


def load_carbon_data() -> pd.DataFrame:
    return pd.read_csv(CARBON_DATA_FILE, index_col="time", parse_dates=True)
