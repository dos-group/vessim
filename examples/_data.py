from vessim.core import HistoricalApi

SOLAR_DATASET = {"actual": "weather_berlin_2021-06.csv", "fill_method": "ffill"}
CARBON_DATASET = {"actual": "carbon_intensity.csv", "fill_method": "ffill"}

SQM = 0.4 * 0.5     # Solar area


def get_solar_time_series_api() -> HistoricalApi:
    return HistoricalApi.from_dataset(
        SOLAR_DATASET, "./data", scale=SQM * .17, start_time="2020-06-01 00:00:00"
    )


def get_ci_time_series_api() -> HistoricalApi:
    return HistoricalApi.from_dataset(CARBON_DATASET, "./data")
