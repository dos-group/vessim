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

        self._actual_index = actual.index.to_numpy(dtype="datetime64[ns]")
        actual_index_sorter = self._actual_index.argsort()
        self._actual_index = self._actual_index[actual_index_sorter]

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
            np_freq = np.timedelta64(frequency)
            forecast_in_freq = self._resample_to_frequency(
                index, forecast, np_start, np_end, np_freq, resample_method
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
            return self._actual_index, self._actual[_get_column_name(self._actual, column)]

        column_name = _get_column_name(self._forecast, column)
        if self._forecast_request_index is None:
            return self._forecast_index, self._forecast[column_name]

        try:
            req_time = self._forecast_request_index[self._forecast_request_index <= start_time][-1]
        except IndexError:
            raise ValueError(f"No forecasts available at time {start_time}.")

        mask = self._forecast_request_index == req_time
        return self._forecast_index[mask], self._forecast[column_name][mask]

    def _resample_to_frequency(
        self,
        index: np.ndarray,
        data: np.ndarray,
        start_time: np.datetime64,
        end_time: np.datetime64,
        frequency: np.timedelta64,
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
                df[start_time] = self.at(start_time, column=str(df.name))
                if resample_method == "ffill":
                    df.ffill(inplace=True)
                else:
                    df.interpolate(method=resample_method, inplace=True)  # type: ignore

        # Get the data to the desired frequency after interpolation
        return df.reindex(new_index[1:])  # type: ignore


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
