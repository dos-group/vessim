from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import timedelta
from pathlib import Path
from typing import Any, Optional, Literal

import pandas as pd
import numpy as np

from vessim._data import load_dataset
from vessim._util import DatetimeLike


class Signal(ABC):
    """Abstract base class for signals."""

    @abstractmethod
    def at(self, dt: DatetimeLike, **kwargs):
        """Retrieves actual data point at given time."""


class HistoricalSignal(Signal):
    """Simulates a signal for time-series data like solar irradiance or carbon intensity.

    The HistoricalSignal can also deal with unsorted or incomplete data.

    Args:
        actual: The actual time-series data to be used. It should contain a datetime-like
            index marking the time, and each column should represent a different zone
            containing the data. The name of the zone is equal to the column name.
            Note that while interpolation is possible when retrieving forecasts, the
            actual data between timestamps is computed using either `ffill` or `bfill`.
            If you wish a different behavior, you have to change your actual data
            beforehand (e.g. by resampling into a different frequency).

        forecast: An optional time-series dataset representing forecasted values. The
            data should contain two datetime-like indices. One is the
            `Request Timestamp`, marking the time when the forecast was made. One is the
            `Forecast Timestamp`, indicating the time the forecast is made for.

            - If data does not include a `Request Timestamp`, it is treated as a static
              forecast that does not change over time.

            - If `forecast` is not provided, predictions are derived from the actual
              data when requesting forecasts (actual data is treated as static forecast).

        fill_method: Either `ffill` or `bfill`. Determines how actual data is acquired in
            between timestamps. Default is `ffill`.
    """

    def __init__(
        self,
        actual: pd.Series | pd.DataFrame,
        forecast: Optional[pd.Series | pd.DataFrame] = None,
        fill_method: Literal["ffill", "bfill"] = "ffill",
    ):
        self._fill_method = fill_method
        # Unpack index of actual dataframe
        actual_times = actual.index.to_numpy(dtype="datetime64[ns]", copy=True)
        actual_times_sorter = actual_times.argsort()
        actual_times = actual_times[actual_times_sorter]

        # Unpack values of actual dataframe
        self._actual: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        if isinstance(actual, pd.Series):
            actual_values = actual.to_numpy(dtype=float, copy=True)[actual_times_sorter]
            nan_mask = ~np.isnan(actual_values)
            self._actual[str(actual.name)] = actual_times[nan_mask], actual_values[nan_mask]
        elif isinstance(actual, pd.DataFrame):
            for col in actual.columns:
                actual_values = actual[col].to_numpy(dtype=float, copy=True)[actual_times_sorter]
                nan_mask = ~np.isnan(actual_values)
                self._actual[str(col)] = actual_times[nan_mask], actual_values[nan_mask]
        else:
            raise ValueError(f"Incompatible type {type(actual)} for 'actual'.")

        # Unpack indices of forecast dataframe if present
        forecast_request_times: Optional[np.ndarray] = None
        if isinstance(forecast, (pd.Series, pd.DataFrame)):
            if isinstance(forecast.index, pd.MultiIndex):
                forecast_request_times = forecast.index.get_level_values(0).to_numpy(
                    dtype="datetime64[ns]", copy=True
                )
                forecast_times = forecast.index.get_level_values(1).to_numpy(
                    dtype="datetime64[ns]", copy=True
                )
                forecast_times_sorter = np.lexsort((forecast_times, forecast_request_times))
                forecast_request_times = forecast_request_times[forecast_times_sorter]
            else:
                forecast_times = forecast.index.to_numpy(dtype="datetime64[ns]", copy=True)
                forecast_times_sorter = np.argsort(forecast_times)
            forecast_times = forecast_times[forecast_times_sorter]

        # Unpack values of forecast dataframe if present
        self._forecast: Optional[dict[str, tuple[Optional[np.ndarray], np.ndarray, np.ndarray]]]
        self._forecast = None
        if forecast_request_times is None:
            req_times = None

        if isinstance(forecast, pd.Series):
            values = forecast.to_numpy(dtype=float, copy=True)[forecast_times_sorter]
            nan_mask = ~np.isnan(values)
            if forecast_request_times is not None:
                req_times = forecast_request_times[nan_mask]
            self._forecast = {
                str(forecast.name): (req_times, forecast_times[nan_mask], values[nan_mask])
            }
        elif isinstance(forecast, pd.DataFrame):
            self._forecast = {}
            for col in forecast.columns:
                values = forecast[col].to_numpy(dtype=float, copy=True)[forecast_times_sorter]
                nan_mask = ~np.isnan(values)
                if forecast_request_times is not None:
                    req_times = forecast_request_times[nan_mask]
                self._forecast[str(col)] = (req_times, forecast_times[nan_mask], values[nan_mask])
        elif forecast is not None:
            raise ValueError(f"Incompatible type {type(forecast)} for 'forecast'.")

    @classmethod
    def from_dataset(
        cls,
        dataset: str,
        data_dir: Optional[str | Path] = None,
        params: Optional[dict[Any, Any]] = None,
    ):
        """Creates a HistoricalSignal from a vessim dataset, handling downloading and unpacking.

        Args:
            dataset: Name of the dataset to be downloaded.
            data_dir: Absoulute path to the directory where the data should be loaded.
                If not specified, the path `~/.cache/vessim` is used. Defaults to None.
            params: Optional extra parameters used for data loading.
                scale (float): Multiplies the data with a factor. Default: 1.0
                start_time (DatetimeLike): Shifts data so that it starts at time. Default: None
                use_forecast (bool): Determines if forecast should be loaded. Default: True
        Raises:
            ValueError if dataset is not available or invalid params are given.
            RuntimeError if dataset can not be loaded.
        """
        if params is None:
            params = {}
        return cls(**load_dataset(dataset, _abs_path(data_dir), params))

    def columns(self) -> list:
        """Returns a list of all columns where actual data is available."""
        return list(self._actual.keys())

    def at(self, dt: DatetimeLike, column: Optional[str] = None, **kwargs) -> float:
        """Retrieves actual data point of zone at given time.

        If queried timestamp is not available in the `actual` dataframe, the fill_method
        is used to determine the data point.

        Args:
            dt: Timestamp, at which data is returned.
            column: Optional column for the data. Has to be provided if there is more than one
                column specified in the data. Defaults to None.
            **kwargs: Possibly needed for subclasses. Are not supported in this class and a
                ValueError will be raised if specified.

        Raises:
            ValueError: If there is no available data at zone or time, or extra kwargs specified.
        """
        if kwargs:
            raise ValueError(f"Invalid arguments: {kwargs.keys()}")

        np_dt = np.datetime64(dt)
        times, values = self._actual[_get_column_name(self._actual, column)]

        if self._fill_method == "ffill":
            index = times.searchsorted(np_dt, side="right") - 1
            if index >= 0:
                return values[index]
            else:
                raise ValueError(f"'{dt}' is too early to get data in column '{column}'.")
        else:
            index = times.searchsorted(np_dt, side="left")
            try:
                return values[index]
            except IndexError:
                raise ValueError(f"'{dt}' is too late to get data in column '{column}'.")

    def forecast(
        self,
        start_time: DatetimeLike,
        end_time: DatetimeLike,
        column: Optional[str] = None,
        frequency: Optional[str | timedelta] = None,
        resample_method: Optional[Literal["ffill", "bfill", "linear", "nearest"]] = None,
    ) -> dict[np.datetime64, float]:
        """Retrieves forecasted data points within window at a frequency.

        - If no separate forecast time-series data is provided, actual data is used.
        - If frequency is not specified, all existing data in the window will be returned.
        - If there is more than one column present, it has to be specified.
        - With specified resampling methods except "bfill", the actual value valid at `start_time`
          is used and because of that, the column where data is aquired has to appear in this data.
        - The forecast does not include the value at `start_time` (see example).

        Args:
            start_time: Starting time of the window.
            end_time: End time of the window.
            column: Optional column where data should be used.
            frequency: Optional interval, in which the forecast data is to be provided.
                Defaults to None.
            resample_method: Optional method, to deal with holes in resampled data.
                Options are `ffill`, `bfill`, `linear` and `nearest`. Defaults to None.

        Returns:
            pd.Series of forecasted data with timestamps of forecast as index.

        Raises:
            ValueError: If no data is available for the specified zone or time, or if
                insufficient data exists for the frequency, without `resample_method`
                specified.

        Example:
            >>> index = pd.date_range(
            ...    "2020-01-01T00:00:00", "2020-01-01T03:00:00", freq="1H"
            ... )
            >>> actual = pd.DataFrame({"zone_a": [4, 6, 2, 8]}, index=index)

            >>> forecast_data = [
            ...    ["2020-01-01T00:00:00", "2020-01-01T01:00:00", 5],
            ...    ["2020-01-01T00:00:00", "2020-01-01T02:00:00", 2],
            ...    ["2020-01-01T00:00:00", "2020-01-01T03:00:00", 6],
            ... ]
            >>> forecast = pd.DataFrame(
            ...    forecast_data, columns=["req_time", "forecast_time", "zone_a"]
            ... )
            >>> forecast.set_index(["req_time", "forecast_time"], inplace=True)

            >>> signal = HistoricalSignal(actual, forecast)

            Forward-fill resampling between 2020-01-01T00:00:00 (actual value = 4.0) and
            forecasted values between 2020-01-01T01:00:00 and 2020-01-01T02:00:00:

            >>> signal.forecast(
            ...    start_time="2020-01-01T00:00:00",
            ...    end_time="2020-01-01T02:00:00",
            ...    frequency="30T",
            ...    resample_method="ffill",
            ... )
            {numpy.datetime64('2020-01-01T00:30:00'): 4.0,
            numpy.datetime64('2020-01-01T01:00:00'): 5.0,
            numpy.datetime64('2020-01-01T01:30:00'): 5.0,
            numpy.datetime64('2020-01-01T02:00:00'): 2.0}

            Time interpolation between 2020-01-01T01:10:00 (actual value = 6.0) and
            2020-01-01T02:00:00 (forecasted value = 2.0):

            >>> signal.forecast(
            ...    start_time="2020-01-01T01:10:00",
            ...    end_time="2020-01-01T01:55:00",
            ...    zone="zone_a",
            ...    frequency=timedelta(minutes=20),
            ...    resample_method="time",
            ... )
            {numpy.datetime64('2020-01-01T01:30:00'): 4.4,
            numpy.datetime64('2020-01-01T01:50:00'): 2.8}
        """
        np_start = np.datetime64(start_time)
        np_end = np.datetime64(end_time)
        if self._forecast is None:
            # No error forecast (actual data is used as static forecast)
            column_name = _get_column_name(self._actual, column)
            times, forecast = self._actual[column_name]
        else:
            column_name = _get_column_name(self._forecast, column)
            req_times, times, forecast = self._forecast[column_name]
            if req_times is not None:
                # Non-static forecast
                req_end_index = np.searchsorted(req_times, np_start, side="right")
                if req_end_index <= 0:
                    raise ValueError(f"No forecasts available at time {start_time}.")
                req_start_index = np.searchsorted(
                    req_times, req_times[req_end_index - 1], side="left"
                )
                times = times[req_start_index:req_end_index]
                forecast = forecast[req_start_index:req_end_index]

        # Resample the data to get the data to specified frequency
        if frequency is not None:
            np_freq = np.timedelta64(pd.to_timedelta(frequency))
            return self._resample_to_frequency(
                times, forecast, column_name, np_start, np_end, np_freq, resample_method
            )

        start_index = np.searchsorted(times, np_start, side="right")
        end_index = np.searchsorted(times, np_end, side="right")
        return dict(
            zip(times[start_index:end_index].copy(), forecast[start_index:end_index].copy())
        )

    def _resample_to_frequency(
        self,
        times: np.ndarray,
        data: np.ndarray,
        column: str,
        start_time: np.datetime64,
        end_time: np.datetime64,
        freq: np.timedelta64,
        resample_method: Optional[Literal["ffill", "bfill", "linear", "nearest"]],
    ) -> dict[np.datetime64, float]:
        """Transform frame into the desired frequency between start and end time."""
        # Cutoff data and create deep copy
        start_index = np.searchsorted(times, start_time, side="right")
        if start_index >= times.size:
            raise ValueError(f"No data found at start time '{start_time}'.")
        end_index = np.searchsorted(times, end_time, side="right") + 1
        times = times[start_index:end_index].copy()
        data = data[start_index:end_index].copy()

        new_times = np.arange(
            start_time + freq, end_time + np.timedelta64(1, "ns"), freq, dtype="datetime64[ns]"
        )

        new_times_indices = np.searchsorted(times, new_times, side="left")
        if not np.array_equal(new_times, times[new_times_indices]) and resample_method != "bfill":
            # Actual value is used for interpolation
            times = np.insert(times, 0, start_time)
            data = np.insert(data, 0, self.at(start_time, column))
            if resample_method == "ffill":
                new_data = data[np.searchsorted(times, new_times, side="right") - 1]
            elif resample_method == "nearest":
                spacing = np.diff(times) / 2
                times = times + np.hstack([spacing, spacing[-1]])
                data = np.hstack([data, data[-1]])
                new_data = data[np.searchsorted(times, new_times)]
            elif resample_method == "linear":
                # Numpy does not support interpolation on datetimes
                new_data = np.interp(new_times.astype("float64"), times.astype("float64"), data)
            elif resample_method is not None:
                raise ValueError(f"Unknown resample_method '{resample_method}'.")
            else:
                raise ValueError(f"Not enough data at frequency '{freq}' without resampling.")
        else:
            new_data = data[new_times_indices]

        return dict(zip(new_times, new_data))


def _get_column_name(data: dict[str, Any], column: Optional[str]) -> str:
    """Extracts data from a dictionary at a key."""
    if column is None:
        if len(data) == 1:
            return next(iter(data.keys()))
        else:
            raise ValueError("Column needs to be specified.")
    elif column in data.keys():
        return column
    else:
        raise ValueError(f"Cannot retrieve data for column '{column}'.")


def _abs_path(data_dir: Optional[str | Path]) -> Path:
    """Returns absolute path to the directory data should be loaded into."""
    if data_dir is None:
        return Path.home() / ".cache" / "vessim"

    path = Path(data_dir).expanduser()
    if path.is_absolute():
        return path
    else:
        raise ValueError(f"Path {data_dir} not valid. Has to be absolute or None.")
