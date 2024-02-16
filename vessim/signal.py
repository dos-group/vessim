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
        self._actual_index = actual.index.to_numpy(dtype="datetime64[ns]")
        actual_index_sorter = self._actual_index.argsort()
        self._actual_index = self._actual_index[actual_index_sorter]

        # Unpack values of actual dataframe
        self._actual: dict[str, np.ndarray] = {}
        if isinstance(actual, pd.Series):
            if self._fill_method == "bfill":
                self._actual[str(actual.name)] = _bfill(actual.to_numpy()[actual_index_sorter])
            else:
                self._actual[str(actual.name)] = _ffill(actual.to_numpy()[actual_index_sorter])
        elif isinstance(actual, pd.DataFrame):
            for col in actual.columns:
                if self._fill_method == "bfill":
                    self._actual[str(col)] = _bfill(actual[col].to_numpy()[actual_index_sorter])
                else:
                    self._actual[str(col)] = _ffill(actual[col].to_numpy()[actual_index_sorter])
        else:
            raise ValueError(f"Incompatible type {type(actual)} for 'actual'.")

        # Unpack indices of forecast dataframe if present
        self._forecast_request_index: Optional[np.ndarray] = None
        self._forecast_index: Optional[np.ndarray] = None
        if isinstance(forecast, (pd.Series, pd.DataFrame)):
            if isinstance(forecast.index, pd.MultiIndex):
                self._forecast_request_index = forecast.index.get_level_values(0).to_numpy(
                    dtype="datetime64[ns]"
                )
                self._forecast_index = forecast.index.get_level_values(1).to_numpy(
                    dtype="datetime64[ns]"
                )
                forecast_index_sorter = np.lexsort((
                    self._forecast_index, self._forecast_request_index
                ))
                self._forecast_request_index = self._forecast_request_index[forecast_index_sorter]
            else:
                self._forecast_index = forecast.index.to_numpy(dtype="datetime64[ns]")
                forecast_index_sorter = np.argsort(self._forecast_index)
            self._forecast_index = self._forecast_index[forecast_index_sorter]

        # Unpack values of forecast dataframe if present
        self._forecast: dict[str, np.ndarray] = {}
        if isinstance(forecast, pd.Series):
            self._forecast[str(forecast.name)] = forecast.to_numpy()[forecast_index_sorter]
        elif isinstance(forecast, pd.DataFrame):
            for col in forecast.columns:
                self._forecast[str(col)] = forecast[col].to_numpy()[forecast_index_sorter]
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

    def at(self, dt: DatetimeLike, column: Optional[str] = None, **kwargs):
        np_dt = np.datetime64(dt)
        values = self._actual[_get_column_name(self._actual, column)]

        if self._fill_method == "ffill":
            time_index = self._actual_index.searchsorted(np_dt, side="right")
            if time_index > 0:
                return values[time_index - 1]
            else:
                raise ValueError(f"'{dt}' is too early to get data in column '{column}'.")
        else:
            time_index = self._actual_index.searchsorted(np_dt, side="left")
            try:
                return values[time_index]
            except IndexError:
                raise ValueError(f"'{dt}' is too late to get data in column '{column}'.")

    def forecast(
        self,
        start_time: DatetimeLike,
        end_time: DatetimeLike,
        column: Optional[str] = None,
        frequency: Optional[str | timedelta] = None,
        resample_method: Optional[str] = None,
    ) -> pd.Series:
        np_start = np.datetime64(start_time)
        np_end = np.datetime64(end_time)
        index, forecast = self._get_forecast_data_source(np_start, column)

        # Resample the data to get the data to specified frequency
        if frequency is not None:
            np_freq = np.timedelta64(pd.to_timedelta(frequency))
            forecast_in_freq = self._resample_to_frequency(
                index, forecast, column, np_start, np_end, np_freq, resample_method
            )

            # Check if there are NaN values in the result
            if forecast_in_freq.hasnans:
                raise ValueError(
                    f"Not enough data for frequency '{frequency}'"
                    f"with resample_method '{resample_method}'."
                )
            return forecast_in_freq

        mask = (np_start < index) & (index <= np_end) & ~np.isnan(forecast)
        return pd.Series(forecast[mask], index=index[mask])

    def _get_forecast_data_source(
        self, start_time: np.datetime64, column: Optional[str]
    ) -> tuple[np.ndarray, np.ndarray]:
        """Returns index and values of column data used to derive forecast prediction."""
        if self._forecast_index is None:
            # No error forecast (actual data is used as static forecast)
            return self._actual_index, self._actual[_get_column_name(self._actual, column)]

        column_name = _get_column_name(self._forecast, column)
        if self._forecast_request_index is None:
            # Static forecast
            return self._forecast_index, self._forecast[column_name]

        # Non-static forecast
        req_index = np.searchsorted(self._forecast_request_index, start_time, side='right') - 1
        if req_index < 0:
            raise ValueError(f"No forecasts available at time {start_time}.")

        mask = self._forecast_request_index == self._forecast_request_index[req_index]
        return self._forecast_index[mask], self._forecast[column_name][mask]

    def _resample_to_frequency(
        self,
        index: np.ndarray,
        data: np.ndarray,
        column: Optional[str],
        start_time: np.datetime64,
        end_time: np.datetime64,
        freq: np.timedelta64,
        resample_method: Optional[str] = None,
    ) -> pd.Series:
        """Transform frame into the desired frequency between start and end time."""
        # Cutoff data for performance
        start_index = np.searchsorted(index, start_time, side="right")
        if start_index >= index.size:
            raise ValueError(f"No data found at start time '{start_time}'.")
        end_index = np.maximum(np.searchsorted(index, end_time, side="right"), index.size)
        index = index[start_index:end_index]
        data = data[start_index:end_index]

        new_index = np.arange(
            start_time + freq, end_time + np.timedelta64(1, "ns"), freq, dtype='datetime64'
        )
        times_to_add = new_index[~np.isin(new_index, index)]

        if times_to_add.size > 0:
            # Resampling is required
            insertion_indices = np.searchsorted(index, times_to_add, side='left')
            index = np.insert(index.copy(), insertion_indices, times_to_add)
            data = np.insert(data.copy(), insertion_indices, np.nan)

            if resample_method == "bfill":
                data = _bfill(data)
            elif resample_method is not None:
                # Insert current actual value at the front for interpolation/forward-fill
                index = np.insert(index, 0, start_time)
                data = np.insert(data, 0, self.at(start_time, column))
                if resample_method == "ffill":
                    data = _ffill(data)
                else:
                    df = pd.Series(data, index=index)
                    df.interpolate(method=resample_method, inplace=True)  # type: ignore
                    return df.reindex(new_index)
            else:
                raise ValueError(f"Not enough data at frequency '{freq}' without resampling.")

        return pd.Series(data[np.isin(index, new_index)], index=new_index)


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
    """Performs forward-fill on a one-dimensional numpy array."""
    mask = np.isnan(arr)
    idx = np.where(~mask, np.arange(mask.size), 0)
    np.maximum.accumulate(idx, out=idx)
    return arr[idx]


def _bfill(arr: np.ndarray) -> np.ndarray:
    """Performs backward-fill on a one-dimensional numpy array."""
    return _ffill(arr[::-1])[::-1]
