"""A simulator for carbon-aware applications and systems."""

from datetime import datetime, timedelta
from typing import Union, List, Optional, Any, Literal

import pandas as pd

DatetimeLike = Union[str, datetime]


class TimeSeriesApi:
    """Simulates an API for time series data like solar irradiance or carbon intensity.

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

            - When using a non-static forecast, you have to be aware that all the
              zones/column names also have to appear in the actual dataframe because some
              actual values are used for interpolation.

        fill_method: Either `ffill` or `bfill`. Determines how actual data is acquired in
            between timestamps. Some data providers like `Solcast` index their data with a
            timestamp marking the end of the time-period that the data is valid for.
            In those cases, `bfill` should be chosen, but the default is `ffill`.

    Example:
        >>> actual_data = [
        ...    ["2020-01-01T00:00:00", 100, 800],
        ...    ["2020-01-01T00:30:00", 110, 850],
        ...    ["2020-01-01T01:00:00", 105, 820],
        ...    ["2020-01-01T01:30:00", 108, 840],
        ... ]
        >>> actual = pd.DataFrame(
        ...    actual_data, columns=["timestamp", "zone_a", "zone_b"]
        ... )
        >>> actual.set_index(["timestamp"], inplace=True)

        >>> forecast_data = [
        ...    ["2020-01-01T00:00:00", "2020-01-01T00:30:00", 115, 850],
        ...    ["2020-01-01T00:00:00", "2020-01-01T01:00:00", 110, 870],
        ...    ["2020-01-01T00:00:00", "2020-01-01T01:30:00", 110, 860],
        ...    ["2020-01-01T00:00:00", "2020-01-01T02:00:00", 120, 830],
        ...    ["2020-01-01T01:00:00", "2020-01-01T01:30:00", 115, 840],
        ...    ["2020-01-01T01:00:00", "2020-01-01T02:00:00", 110, 830],
        ... ]
        >>> forecast = pd.DataFrame(
        ...    forecast_data, columns=["req_time", "forecast_time", "zone_a", "zone_b"]
        ... )
        >>> forecast.set_index(["req_time", "forecast_time"], inplace=True)

        >>> time_series = TimeSeriesApi(actual, forecast)
    """

    def __init__(
        self,
        actual: Union[pd.Series, pd.DataFrame],
        forecast: Optional[Union[pd.Series, pd.DataFrame]] = None,
        fill_method: Literal["ffill", "bfill"] = "ffill",
    ):
        actual.index = pd.to_datetime(actual.index)
        actual.sort_index(inplace=True)
        if isinstance(actual, pd.Series):
            self._actual = actual.to_frame()
        elif isinstance(actual, pd.DataFrame):
            self._actual = actual
        else:
            raise ValueError(f"Incompatible type {type(actual)} for 'actual'.")

        if isinstance(forecast, (pd.Series, pd.DataFrame)):
            # Convert all indices (either one or two columns) to datetime
            if isinstance(forecast.index, pd.MultiIndex):
                forecast_index: pd.MultiIndex = forecast.index
                for level in range(forecast.index.nlevels):
                    forecast.index = forecast_index.set_levels(
                        pd.to_datetime(forecast_index.levels[level]), level=level
                    )
            else:
                forecast.index = pd.to_datetime(forecast.index)

            forecast.sort_index(inplace=True)
        self._forecast: Optional[pd.DataFrame]
        if isinstance(forecast, pd.Series):
            self._forecast = forecast.to_frame()
        else:
            self._forecast = forecast  # type: ignore
        self._fill_method = fill_method

    def zones(self) -> List:
        """Returns a list of all zones, where actual data is available."""
        return list(self._actual.columns)

    def actual(self, dt: DatetimeLike, zone: Optional[str] = None) -> Any:
        """Retrieves actual data point of zone at given time.

        If queried timestamp is not available in the `actual` dataframe, the last valid
        datapoint is being returned.

        Args:
            dt: Timestamp, at which the data is needed.
            zone: Optional zone for the data. Has to be provided if there is more than one
                zone specified in the data. Defaults to None.

        Raises:
            ValueError: If there is no available data at specified zone or time.
        """
        data_at_time = self._get_actual_values_at_time(dt)
        zone_index = self._get_zone_index_from_dataframe(data_at_time, zone)

        data_point = data_at_time.iloc[0, zone_index]
        if pd.isna(data_point):
            raise ValueError(f"Cannot retrieve actual data at '{dt}' in zone '{zone}'.")
        return data_point

    def forecast(
        self,
        start_time: DatetimeLike,
        end_time: DatetimeLike,
        zone: Optional[str] = None,
        frequency: Optional[Union[str, pd.DateOffset, timedelta]] = None,
        resample_method: Optional[str] = None,
    ) -> pd.Series:
        """Retrieves of forecasted data points within window at a frequency.

        - If no forecast time-series data is provided, actual data is used.
        - Specified timestamps are always rounded down to the nearest existing.
        - If frequency is not specified, all existing data in the window will be returned.
        - For various resampling methods, the actual value valid at `start_time` is used.
          So you have to make sure that there is a valid actual value.
        - If there is more than one zone present in the data, zone has to be specified.
          (Note that zone name must also appear in actual data for non-static forecast.)
        - The forecast does not include the value at `start_time` (see example).

        Args:
            start_time: Starting time of the window.
            end_time: End time of the window.
            zone: Optional geographical zone of the forecast. Defaults to None.
            frequency: Optional interval, in which the forecast data is to be provided.
                Defaults to None.
            resample_method: Optional method, to deal with holes in resampled data.
                Can be either `bfill`, `ffill` or an interpolation method.
                For more information on interpolation methods, see the
                `pandas documentation <https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.interpolate.html>`_.

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

            >>> time_series = TimeSeriesApi(actual, forecast)

            Forward-fill resampling between 2020-01-01T00:00:00 (actual value = 4.0) and
            forecasted values between 2020-01-01T01:00:00 and 2020-01-01T02:00:00:

            >>> time_series.forecast(
            ...    start_time="2020-01-01T00:00:00",
            ...    end_time="2020-01-01T02:00:00",
            ...    frequency="30T",
            ...    resample_method="ffill",
            ... )
            2020-01-01 00:30:00    4.0
            2020-01-01 01:00:00    5.0
            2020-01-01 01:30:00    5.0
            2020-01-01 02:00:00    2.0
            Freq: 30T, Name: zone_a, dtype: float64

            Time interpolation between 2020-01-01T01:10:00 (actual value = 6.0) and
            2020-01-01T02:00:00 (forecasted value = 2.0):

            >>> time_series.forecast(
            ...    start_time="2020-01-01T01:10:00",
            ...    end_time="2020-01-01T01:55:00",
            ...    zone="zone_a",
            ...    frequency=timedelta(minutes=20),
            ...    resample_method="time",
            ... )
            2020-01-01 01:30:00    4.4
            2020-01-01 01:50:00    2.8
            Freq: 20T, Name: zone_a, dtype: float64
        """
        data_src = self._get_forecast_data_source(start_time)

        zone_index = self._get_zone_index_from_dataframe(data_src, zone)

        # Get data of zone and convert to pd.Series
        forecast: pd.Series = data_src.iloc[:, zone_index].squeeze()

        # Resample the data to get the data to specified frequency
        if frequency is not None:
            forecast = self._resample_to_frequency(
                forecast, start_time, end_time, frequency, resample_method=resample_method
            )
            return forecast.iloc[1:]

        return forecast.loc[(forecast.index > start_time) & (forecast.index <= end_time)]

    def _get_forecast_data_source(self, start_time: DatetimeLike):
        """Returns dataframe used to derive forecast prediction."""
        data_src: pd.DataFrame
        if self._forecast is None:
            # Get all data points beginning at the nearest existing timestamp
            # lower than start time from actual data
            data_src = self._actual.loc[self._actual.index.asof(start_time) :]
        elif self._forecast.index.nlevels == 1:
            # Forecast data does not include request_timestamp
            data_src = self._forecast.loc[self._forecast.index.asof(start_time) :]
        else:
            # Get forecasts of the nearest existing timestamp lower than start time
            first_index = self._forecast.index.get_level_values(0)
            request_time = first_index[first_index <= start_time][-1]
            data_src = self._forecast.loc[request_time]  # type: ignore

            # Retrieve the actual value at start_time and attach it to the front of the
            # forecast data with the timestamp (for interpolation at a later stage)
            actual_values = self._get_actual_values_at_time(start_time)
            data_src = pd.concat(
                [actual_values, data_src.loc[(data_src.index > start_time)]]
            )

        if data_src.empty:
            raise ValueError(f"Cannot retrieve forecast data at '{start_time}'.")

        return data_src

    def _get_actual_values_at_time(self, dt: DatetimeLike) -> pd.DataFrame:
        """Return actual data that is valid at a specific time."""
        return self._actual.reindex(index=[pd.to_datetime(dt)], method=self._fill_method)

    def _get_zone_index_from_dataframe(self, df: pd.DataFrame, zone: Optional[str]):
        """Return column index of zone from given dataframe.

        If zone is not specified, but there is only one column in the dataframe, the
        first index is returned.

        Raises:
            ValueError: If zone index can not be determined.
        """
        if zone is None:
            if len(df.columns) == 1:
                zone_index = 0
            else:
                raise ValueError("Zone needs to be specified.")
        else:
            try:
                zone_index = df.columns.get_loc(zone)
            except KeyError:
                raise ValueError(f"Cannot retrieve data for zone '{zone}'.")

        return zone_index

    def _resample_to_frequency(
        self,
        df: pd.Series,
        start_time: DatetimeLike,
        end_time: DatetimeLike,
        frequency: Optional[Union[str, pd.DateOffset, timedelta]] = None,
        resample_method: Optional[str] = None,
    ):
        """Transform series into the desired frequency between start and end time."""
        frequency = pd.tseries.frequencies.to_offset(frequency)
        if frequency is None:
            raise ValueError(f"Frequency '{frequency}' invalid.")

        # Add NaN values in the specified frequency
        new_index = pd.date_range(start=start_time, end=end_time, freq=frequency)
        combined_index = df.index.union(new_index).sort_values()
        df = df.reindex(combined_index)

        # Use specific resample method if specified to fill NaN values
        if resample_method == "ffill":
            df.ffill(inplace=True)
        elif resample_method == "bfill":
            df.bfill(inplace=True)
        elif resample_method is not None:
            df.interpolate(method=resample_method, inplace=True)  # type: ignore
        elif df.isnull().values.any():  # type: ignore
            # Check if there are NaN values if resample method is not specified
            raise ValueError(
                f"Not enough data at frequency '{frequency}'. Specify resample_method"
            )

        # Get the data to the desired frequency after interpolation
        return df.loc[(df.index >= start_time) & (df.index <= end_time)].asfreq(frequency)

    def next_update(self, dt: DatetimeLike) -> datetime:
        """Returns the next time of when the actual trace will change.

        This method is being called in the time-based simulation model for Mosaik.
        """
        current_index = self._actual.index.asof(dt)
        next_iloc = self._actual.index.get_loc(current_index) + 1
        return self._actual.index[next_iloc]
