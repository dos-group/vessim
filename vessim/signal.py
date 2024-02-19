from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import timedelta
from pathlib import Path
from typing import Any, Optional, Literal

import pandas as pd
import numpy as np

from vessim._data import load_dataset
from vessim.util import DatetimeLike


class Signal(ABC):
    """Abstract base class for APIs."""

    @abstractmethod
    def at(self, dt: DatetimeLike, **kwargs):
        """Retrieves actual data point at given time."""


class HistoricalSignal(Signal):
    def __init__(
        self,
        actual: pd.Series | pd.DataFrame,
        forecast: Optional[pd.Series | pd.DataFrame] = None,
        fill_method: Literal["ffill", "bfill"] = "ffill",
    ):
        self._fill_method = fill_method
        # Unpack index of actual dataframe
        self._actual_times = actual.index.to_numpy(dtype="datetime64[s]", copy=True)
        actual_times_sorter = self._actual_times.argsort()
        self._actual_times = self._actual_times[actual_times_sorter]

        # Unpack values of actual dataframe
        self._actual: dict[str, np.ndarray] = {}
        if isinstance(actual, pd.Series):
            if self._fill_method == "bfill":
                self._actual[str(actual.name)] = _bfill(
                    actual.to_numpy(dtype="float64", copy=True)[actual_times_sorter]
                )
            else:
                self._actual[str(actual.name)] = _ffill(
                    actual.to_numpy(dtype="float64", copy=True)[actual_times_sorter]
                )
        elif isinstance(actual, pd.DataFrame):
            for col in actual.columns:
                if self._fill_method == "bfill":
                    self._actual[str(col)] = _bfill(
                        actual[col].to_numpy(dtype="float64", copy=True)[actual_times_sorter]
                    )
                else:
                    self._actual[str(col)] = _ffill(
                        actual[col].to_numpy(dtype="float64", copy=True)[actual_times_sorter]
                    )
        else:
            raise ValueError(f"Incompatible type {type(actual)} for 'actual'.")

        # Unpack indices of forecast dataframe if present
        self._forecast_request_times: Optional[np.ndarray] = None
        self._forecast_times: Optional[np.ndarray] = None
        if isinstance(forecast, (pd.Series, pd.DataFrame)):
            if isinstance(forecast.index, pd.MultiIndex):
                self._forecast_request_times = forecast.index.get_level_values(0).to_numpy(
                    dtype="datetime64[s]", copy=True
                )
                self._forecast_times = forecast.index.get_level_values(1).to_numpy(
                    dtype="datetime64[s]", copy=True
                )
                forecast_times_sorter = np.lexsort(
                    (self._forecast_times, self._forecast_request_times)
                )
                self._forecast_request_times = self._forecast_request_times[forecast_times_sorter]
            else:
                self._forecast_times = forecast.index.to_numpy(dtype="datetime64[s]", copy=True)
                forecast_times_sorter = np.argsort(self._forecast_times)
            self._forecast_times = self._forecast_times[forecast_times_sorter]

        # Unpack values of forecast dataframe if present
        self._forecast: dict[str, np.ndarray] = {}
        if isinstance(forecast, pd.Series):
            self._forecast[str(forecast.name)] = forecast.to_numpy(dtype="float64", copy=True)[
                forecast_times_sorter
            ]
        elif isinstance(forecast, pd.DataFrame):
            for col in forecast.columns:
                self._forecast[str(col)] = forecast[col].to_numpy(dtype="float64", copy=True)[
                    forecast_times_sorter
                ]
        elif forecast is not None:
            raise ValueError(f"Incompatible type {type(forecast)} for 'forecast'.")

    @classmethod
    def from_dataset(
        cls,
        dataset: str,
        data_dir: Optional[str | Path] = None,
        params: Optional[dict[Any, Any]] = None,
    ):
        if params is None:
            params = {}
        return cls(**load_dataset(dataset, _abs_path(data_dir), params))

    def columns(self) -> list:
        """Returns a list of all columns where actual data is available."""
        return list(self._actual.keys())

    def at(self, dt: DatetimeLike, column: Optional[str] = None, **kwargs) -> float:
        np_dt = np.datetime64(dt)
        values = self._actual[_get_column_name(self._actual, column)]

        if self._fill_method == "ffill":
            index = self._actual_times.searchsorted(np_dt, side="right") - 1
            if index >= 0:
                return values[index].astype(float)
            else:
                raise ValueError(f"'{dt}' is too early to get data in column '{column}'.")
        else:
            index = self._actual_times.searchsorted(np_dt, side="left")
            try:
                return values[index].astype(float)
            except IndexError:
                raise ValueError(f"'{dt}' is too late to get data in column '{column}'.")

    def forecast(
        self,
        start_time: DatetimeLike,
        end_time: DatetimeLike,
        column: Optional[str] = None,
        frequency: Optional[str | timedelta] = None,
        resample_method: Optional[str] = None,
    ) -> dict[np.datetime64, float]:
        np_start = np.datetime64(start_time)
        np_end = np.datetime64(end_time)
        times, forecast = self._get_forecast_data_source(np_start, column)

        nan_mask = ~np.isnan(forecast)
        times = times[nan_mask]
        forecast = forecast[nan_mask]

        # Resample the data to get the data to specified frequency
        if frequency is not None:
            np_freq = np.timedelta64(pd.to_timedelta(frequency))
            return self._resample_to_frequency(
                times, forecast, column, np_start, np_end, np_freq, resample_method
            )

        start_index = np.searchsorted(times, np_start, side="right")
        end_index = np.searchsorted(times, np_end, side="right")
        return {
            time: value.astype(float) for time, value in zip(
                times[start_index:end_index].copy(), forecast[start_index:end_index].copy()
            )
        }

    def _get_forecast_data_source(
        self, start_time: np.datetime64, column: Optional[str]
    ) -> tuple[np.ndarray, np.ndarray]:
        """Returns index and values of column data used to derive forecast prediction."""
        if self._forecast_times is None:
            # No error forecast (actual data is used as static forecast)
            return self._actual_times, self._actual[_get_column_name(self._actual, column)]

        column_name = _get_column_name(self._forecast, column)
        if self._forecast_request_times is None:
            # Static forecast
            return self._forecast_times, self._forecast[column_name]

        # Non-static forecast
        req_end_index = np.searchsorted(self._forecast_request_times, start_time, side="right")
        if req_end_index <= 0:
            raise ValueError(f"No forecasts available at time {start_time}.")
        req_start_index = np.searchsorted(
            self._forecast_request_times,
            self._forecast_request_times[req_end_index - 1],
        )
        return (
            self._forecast_times[req_start_index:req_end_index],
            self._forecast[column_name][req_start_index:req_end_index],
        )

    def _resample_to_frequency(
        self,
        times: np.ndarray,
        data: np.ndarray,
        column: Optional[str],
        start_time: np.datetime64,
        end_time: np.datetime64,
        freq: np.timedelta64,
        resample_method: Optional[str],
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
            start_time + freq, end_time + np.timedelta64(1, "s"), freq, dtype="datetime64[s]"
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
                new_data = np.interp(
                    new_times.astype("float64"), times.astype("float64"), data
                )
            elif resample_method is not None:
                raise ValueError(f"Unknown resample_method '{resample_method}'.")
            else:
                raise ValueError(f"Not enough data at frequency '{freq}' without resampling.")
        else:
            new_data = data[new_times_indices]

        return {time: value.astype(float) for time, value in zip(new_times, new_data)}


def _get_column_name(data: dict[str, Any], column: Optional[str]) -> str:
    if column is None:
        if len(data) == 1:
            return list(data.keys())[0]
        else:
            raise ValueError("Column needs to be specified.")
    elif column in data.keys():
        return column
    else:
        raise ValueError(f"Cannot retrieve data for column '{column}'.")


def _abs_path(data_dir: Optional[str | Path]):
    if data_dir is None:
        return Path.home() / ".cache" / "vessim"

    path = Path(data_dir).expanduser()
    if path.is_absolute():
        return path
    else:
        raise ValueError(f"Path {data_dir} not valid. Has to be absolute or None.")


def _ffill(arr: np.ndarray) -> np.ndarray:
    """Fills up NaN values of array using forward-fill."""
    mask = np.isnan(arr)
    idx = np.where(~mask, np.arange(mask.size), 0)
    np.maximum.accumulate(idx, out=idx)
    return arr[idx]


def _bfill(arr: np.ndarray) -> np.ndarray:
    """Fills up NaN values of array using backward-fill."""
    return _ffill(arr[::-1])[::-1]
