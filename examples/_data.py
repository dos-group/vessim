import os
from datetime import timedelta

from vessim import TimeSeriesApi
from vessim.datasets import DataLoader

BASE_DIR = f"{os.path.dirname(__file__)}/data"
SOLAR_DATA_FILE = "weather_berlin_2021-06.csv"
CARBON_DATA_FILE = "carbon_intensity.csv"

data = DataLoader(BASE_DIR)

def transform_solar_data(solar_data, sqm: float):
    solar_data.index -= timedelta(days=365)
    return solar_data * sqm * .17  # W/m^2 * m^2 = W


def get_solar_time_series_api() -> TimeSeriesApi:
    return data.get_time_series_api(
        actual_file_name = SOLAR_DATA_FILE,
        actual_index_col = "time",
        actual_value_cols=["solar"],
        actual_transform=transform_solar_data,
        sqm=0.4 * 0.5,
    )


def get_ci_time_series_api() -> TimeSeriesApi:
    return data.get_time_series_api(CARBON_DATA_FILE, actual_index_col="time")
