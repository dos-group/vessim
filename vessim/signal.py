from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import timedelta, datetime
from pathlib import Path
from typing import Any, Optional, Literal

import pandas as pd

from vessim._data import convert_to_datetime, load_dataset
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
        actual = convert_to_datetime(actual)
        self._actual: dict[str, pd.Series]
        if isinstance(actual, pd.Series):
            self._actual = {str(actual.name): actual.dropna()}
        elif isinstance(actual, pd.DataFrame):
            self._actual = {col: actual[col].dropna() for col in actual.columns}
        else:
            raise ValueError(f"Incompatible type {type(actual)} for 'actual'.")
        self._fill_method = fill_method

        self._forecast: dict[str, pd.Series]
        if isinstance(forecast, pd.Series):
            forecast = convert_to_datetime(forecast)
            self._forecast = {str(forecast.name): forecast.dropna()} # type: ignore
        elif isinstance(forecast, pd.DataFrame):
            forecast = convert_to_datetime(forecast)
            self._forecast = {
                str(col): forecast[col].dropna() for col in forecast.columns  # type: ignore
            }
        elif forecast is None:
            self._forecast = {
                str(key): data.copy(deep=True) for key, data in self._actual.items()
            }
        else:
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
        dt = pd.to_datetime(dt)
        column_data = _get_column_data(self._actual, column)

        # Mypy somehow has trouble with indexing in a dataframe with DatetimeIndex
        # <https://github.com/python/mypy/issues/2410>
        if self._fill_method == "ffill":
            # searchsorted with 'side' specified in sorted df always returns an int
            time_index: int = column_data.index.searchsorted(dt, side="right")  # type: ignore
            if time_index > 0:
                return column_data.iloc[time_index - 1]  # type: ignore
            else:
                raise ValueError(f"'{dt}' is too early to get data in column "
                                 f"'{column}'.")
        else:
            time_index = column_data.index.searchsorted(dt, side="left")  # type: ignore
            try:
                return column_data.iloc[time_index]  # type: ignore
            except IndexError:
                raise ValueError(
                    f"'{dt}' is too late to get data in column '{column}'."
                )


    def forecast(
        self,
        start_time: DatetimeLike,
        end_time: DatetimeLike,
        column: Optional[str] = None,
        frequency: Optional[str | pd.DateOffset | timedelta] = None,
        resample_method: Optional[str] = None,
    ) -> pd.Series:
        start_time = pd.to_datetime(start_time)
        end_time = pd.to_datetime(end_time)
        forecast: pd.Series = self._get_forecast_data_source(start_time, column)

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
        self, start_time: datetime, column: Optional[str]
    ) -> pd.Series:
        """Returns series of column data used to derive forecast prediction."""
        data_src = _get_column_data(self._forecast, column)

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
                df[start_time] = self.at(start_time, column=str(df.name))
                if resample_method == "ffill":
                    df.ffill(inplace=True)
                else:
                    df.interpolate(method=resample_method, inplace=True)  # type: ignore

        # Get the data to the desired frequency after interpolation
        return df.reindex(new_index[1:])  # type: ignore


def _get_column_data(data: dict[str, pd.Series], column: Optional[str]) -> pd.Series:
    if column is None:
        if len(data) == 1:
            return next(iter(data.values()))
        else:
            raise ValueError("Column needs to be specified.")
    try:
        return data[column]
    except KeyError:
        raise ValueError(f"Cannot retrieve data for column '{column}'.")


def _abs_path(data_dir: Optional[str | Path]):
    if data_dir is None:
        return Path.home() / ".cache" / "vessim"

    path = Path(data_dir).expanduser()
    if path.is_absolute():
        return path
    else:
        raise ValueError(f"Path {data_dir} not valid. Has to be absolute or None.")
