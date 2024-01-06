from pathlib import Path
from datetime import timedelta

from vessim import TimeSeriesApi
from vessim.data import read_data_from_csv

BASE_DIR = Path(__file__).parent.resolve() / "data"
SOLAR_DATA_FILE = BASE_DIR / "weather_berlin_2021-06.csv"
CARBON_DATA_FILE = BASE_DIR / "carbon_intensity.csv"

SQM = 0.4 * 0.5     # Solar area


def get_solar_time_series_api() -> TimeSeriesApi:
    return TimeSeriesApi(actual=read_data_from_csv(
        path=SOLAR_DATA_FILE,
        index_cols="time",
        scale=SQM * .17, # W/m^2 * m^2 = W
        shift=timedelta(days=-365),
    ))


def get_ci_time_series_api() -> TimeSeriesApi:
    return TimeSeriesApi(actual=read_data_from_csv(CARBON_DATA_FILE, index_cols="time"))
