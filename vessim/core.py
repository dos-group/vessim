from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime, timedelta
from typing import Union, List, Optional, Literal, Dict, Hashable

import pandas as pd

from vessim.data import load_dataset, convert_to_datetime, DatetimeLike


class Api(ABC):
    """Abstract base class for APIs."""

    @abstractmethod
    def actual(self, now: DatetimeLike, **kwargs):
        """Retrieves actual data point at given time."""


class ForecastMixin(ABC):

    @abstractmethod
    def forecast(self, start_time: DatetimeLike, **kwargs) -> pd.Series:
        """Retrieves forecasted data points."""


class HistoricalApi(Api):

    def __init__(
        self,
        actual: Union[pd.Series, pd.DataFrame],
        fill_method: Literal["ffill", "bfill"] = "bfill",
    ):
        actual = convert_to_datetime(actual)
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
        return cls(**load_dataset(dataset, _abs_path(data_dir), scale, start_time))

    def endpoints(self) -> List:
        """Returns a list of all endpoints, where actual data is available."""
        return list(self._actual.keys())

    def actual(self, now: DatetimeLike, endpoint: Optional[str] = None):
        dt = pd.to_datetime(now)
        endpoint_data = _get_endpoint_data(self._actual, endpoint)

        # Mypy somehow has trouble with indexing in a dataframe with DatetimeIndex
        # <https://github.com/python/mypy/issues/2410>
        if self._fill_method == "ffill":
            # searchsorted with 'side' specified in sorted df always returns an int
            time_index: int = endpoint_data.index.searchsorted(dt, side="right")  # type: ignore
            if time_index > 0:
                return endpoint_data.iloc[time_index - 1]  # type: ignore
            else:
                raise ValueError(f"'{dt}' is too early to get data in endpoint '{endpoint}'.")
        else:
            time_index = endpoint_data.index.searchsorted(dt, side="left")  # type: ignore
            try:
                return endpoint_data.iloc[time_index]  # type: ignore
            except IndexError:
                raise ValueError(f"'{dt}' is too late to get data in endpoint '{endpoint}'.")


class HistoricalForecastApi(HistoricalApi, ForecastMixin):

    def __init__(
        self,
        actual: Union[pd.Series, pd.DataFrame],
        forecast: Optional[Union[pd.Series, pd.DataFrame]] = None,
        fill_method: Literal["ffill", "bfill"] = "bfill",
    ):
        super().__init__(actual=actual, fill_method=fill_method)

        self._forecast: Dict[Hashable, pd.Series]
        if isinstance(forecast, pd.Series):
            forecast = convert_to_datetime(forecast)
            self._forecast = {forecast.name: forecast.dropna()}
        elif isinstance(forecast, pd.DataFrame):
            forecast = convert_to_datetime(forecast)
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
        return cls(**load_dataset(dataset, _abs_path(data_dir), scale, start_time,
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


class WatttimeApi(Api, ForecastMixin):

    def actual(self, dt: DatetimeLike, params: Optional[Dict] = None):
        pass

    def forecast(self, dt: DatetimeLike, params: Optional[Dict] = None):
        pass


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
