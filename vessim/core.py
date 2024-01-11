from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime, timedelta
from typing import Union, List, Optional, Literal, Dict, Hashable

import pandas as pd

from vessim.data import _load_dataset, _convert_to_datetime, DatetimeLike

import requests
from requests.auth import HTTPBasicAuth

class Api(ABC):
    """Abstract base class for APIs."""

    @abstractmethod
    def actual(self, now: DatetimeLike, **kwargs):
        """Retrieves actual data point at given time."""


class HistoricalApi(Api):

    def __init__(
        self,
        actual: Union[pd.Series, pd.DataFrame],
        fill_method: Literal["ffill", "bfill"] = "ffill",
    ):
        actual = _convert_to_datetime(actual)
        self._actual: Dict[Hashable, pd.Series]
        if isinstance(actual, pd.Series):
            self._actual = {actual.name: actual.dropna()}
        elif isinstance(actual, pd.DataFrame):
            self._actual = {col: actual[col].dropna() for col in actual.columns}
        else:
            raise ValueError(f"Incompatible type {type(actual)} for 'actual'.")
        self._fill_method = fill_method

    @classmethod
    def from_dataset(
        cls,
        dataset: Union[str, Dict],
        data_dir: Union[str, Path] = ".",
        scale: float = 1.0,
        start_time: Optional[DatetimeLike] = None,
    ):
        return cls(**_load_dataset(dataset, _abs_path(data_dir), scale, start_time))

    def endpoints(self) -> List:
        """Returns a list of all endpoints, where actual data is available."""
        return list(self._actual.keys())

    def actual(self, now: DatetimeLike, endpoint: Optional[str] = None):
        now = pd.to_datetime(now)
        endpoint_data = _get_endpoint_data(self._actual, endpoint)

        # Mypy somehow has trouble with indexing in a dataframe with DatetimeIndex
        # <https://github.com/python/mypy/issues/2410>
        if self._fill_method == "ffill":
            # searchsorted with 'side' specified in sorted df always returns an int
            time_index: int = endpoint_data.index.searchsorted(now, side="right")  # type: ignore
            if time_index > 0:
                return endpoint_data.iloc[time_index - 1]  # type: ignore
            else:
                raise ValueError(f"'{now}' is too early to get data in endpoint '{endpoint}'.")
        else:
            time_index = endpoint_data.index.searchsorted(now, side="left")  # type: ignore
            try:
                return endpoint_data.iloc[time_index]  # type: ignore
            except IndexError:
                raise ValueError(f"'{now}' is too late to get data in endpoint '{endpoint}'.")


class HistoricalForecastApi(HistoricalApi):

    def __init__(
        self,
        actual: Union[pd.Series, pd.DataFrame],
        forecast: Optional[Union[pd.Series, pd.DataFrame]] = None,
        fill_method: Literal["ffill", "bfill"] = "ffill",
    ):
        super().__init__(actual=actual, fill_method=fill_method)

        self._forecast: Dict[Hashable, pd.Series]
        if isinstance(forecast, pd.Series):
            forecast = _convert_to_datetime(forecast)
            self._forecast = {forecast.name: forecast.dropna()}
        elif isinstance(forecast, pd.DataFrame):
            forecast = _convert_to_datetime(forecast)
            self._forecast = {col: forecast[col].dropna() for col in forecast.columns}
        elif forecast is None:
            self._forecast = {
                key: data.copy(deep=True) for key, data in self._actual.items()
            }
        else:
            raise ValueError(f"Incompatible type {type(forecast)} for 'forecast'.")

    @classmethod
    def from_dataset(
        cls,
        dataset: Union[str, Dict],
        data_dir: Union[str, Path] = ".",
        scale: float = 1.0,
        start_time: Optional[DatetimeLike] = None,
    ):
        return cls(**_load_dataset(dataset, _abs_path(data_dir), scale, start_time,
                                  use_forecast=True))

    def forecast(
        self,
        start_time: DatetimeLike,
        end_time: DatetimeLike,
        endpoint: Optional[str] = None,
        frequency: Optional[Union[str, pd.DateOffset, timedelta]] = None,
        resample_method: Optional[str] = None,
    ) -> pd.Series:
        start_time = pd.to_datetime(start_time)
        end_time = pd.to_datetime(end_time)
        forecast: pd.Series = self._get_forecast_data_source(start_time, endpoint)

        # Resample the data to get the data to specified frequency
        if frequency is not None:
            frequency = pd.tseries.frequencies.to_offset(frequency)
            if frequency is None:
                raise ValueError(f"Frequency '{frequency}' invalid.")

            forecast_in_freq = self._resample_to_frequency(
                forecast, start_time, end_time, frequency, resample_method
            )

            # Check if there are NaN values in the result
            if forecast_in_freq.hasnans:
                raise ValueError(
                    f"Not enough data for frequency '{frequency}'"
                    f"with resample_method '{resample_method}'."
                )
            return forecast_in_freq

        start_index = forecast.index.searchsorted(start_time, side="right")
        return forecast.loc[forecast.index[start_index] : end_time]  # type: ignore

    def _get_forecast_data_source(
        self, start_time: datetime, endpoint: Optional[str]
    ) -> pd.Series:
        """Returns series of endpoint data used to derive forecast prediction."""
        data_src = _get_endpoint_data(self._forecast, endpoint)

        if data_src.index.nlevels > 1:
            # Forecast does include request timestamp
            try:
                # Get forecasts of the nearest existing timestamp lower than start time
                req_time = data_src[:start_time].index.get_level_values(0)[-1]  # type: ignore
            except IndexError:
                raise ValueError(f"No forecasts available at time {start_time}.")
            data_src = data_src.loc[req_time]

        return data_src

    def _resample_to_frequency(
        self,
        df: pd.Series,
        start_time: datetime,
        end_time: datetime,
        frequency: pd.DateOffset,
        resample_method: Optional[str] = None,
    ) -> pd.Series:
        """Transform frame into the desired frequency between start and end time."""
        new_index = pd.date_range(start=start_time, end=end_time, freq=frequency)

        if resample_method is not None:
            # Cutoff data for performance
            try:
                cutoff_time = df.index[df.index.searchsorted(end_time, side="right")]
                df = df.loc[start_time:cutoff_time]  # type: ignore
            except IndexError:
                df = df.loc[start_time:]  # type: ignore
            # Add NaN values in the specified frequency
            combined_index = df.index.union(new_index, sort=True)
            df = df.reindex(combined_index)

            # Use specific resample method if specified to fill NaN values
            if resample_method == "bfill":
                df.bfill(inplace=True)
            elif resample_method is not None:
                # Add actual value to front of series because needed for interpolation
                df[start_time] = self.actual(start_time, endpoint=str(df.name))
                if resample_method == "ffill":
                    df.ffill(inplace=True)
                else:
                    df.interpolate(method=resample_method, inplace=True)  # type: ignore

        # Get the data to the desired frequency after interpolation
        return df.reindex(new_index[1:])  # type: ignore


class WatttimeApi(Api):
    _URL = "https://api.watttime.org"

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.headers = {"Authorization": f"Bearer {self._login()}"}

    def actual(self, now: DatetimeLike, region: str = None, signal_type: str = "co2_moer"):
        if region is None:
            raise ValueError("Region needs to be specified.")
        now = pd.to_datetime(now)
        rsp = self._request("/historical", params={
            "region": region,
            "start": (now - timedelta(minutes=5)).isoformat(),
            "end": now.isoformat(),
            "signal_type": signal_type,
        })
        return rsp

    def _request(self, endpoint: str, params: Dict):
        while True:
            rsp = requests.get(f"{self._URL}/v3{endpoint}", headers=self.headers, params=params)
            if rsp.status_code == 200:
                return rsp.json()["data"][0]["value"]
            if rsp.status_code == 400:
                return f"Error {rsp.status_code}: {rsp.json()}"
            elif rsp.status_code in [401, 403]:
                self.headers["Authorization"] = f"Bearer {self._login()}"
            else:
                raise ValueError(f"Error {rsp.status_code}: {rsp}")

    def _login(self) -> str:
        # TODO reconnect if token is expired
        rsp = requests.get(f"{self._URL}/login", auth=HTTPBasicAuth(self.username, self.password))
        return rsp.json()['token']


def _get_endpoint_data(data: Dict[str, pd.Series], endpoint: Optional[str]) -> pd.Series:
    if endpoint is None:
        if len(data) == 1:
            return next(iter(data.values()))
        else:
            raise ValueError("Endpoint needs to be specified.")
    try:
        return data[endpoint]
    except KeyError:
        raise ValueError(f"Cannot retrieve data for endpoint '{endpoint}'.")


def _abs_path(data_dir: str):
    data_dir = Path(data_dir)
    if data_dir.is_absolute():
        return data_dir
    return Path(__file__).parent / data_dir
