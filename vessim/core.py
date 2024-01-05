from datetime import timedelta, datetime
from typing import Union, Optional, Literal, Dict, Hashable, List, Any

import pandas as pd

from vessim import DatetimeLike


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
        self._actual: Dict[Hashable, pd.Series]
        if isinstance(actual, pd.Series):
            self._actual = {actual.name: actual.dropna()}
        elif isinstance(actual, pd.DataFrame):
            self._actual = {col: actual[col].dropna() for col in actual.columns}
        else:
            raise ValueError(f"Incompatible type {type(actual)} for 'actual'.")

        if isinstance(forecast, (pd.Series, pd.DataFrame)):
            # Convert all indices (either one or two columns) to datetime
            if isinstance(forecast.index, pd.MultiIndex):
                index: pd.MultiIndex = forecast.index
                for i, level in enumerate(index.levels):
                    index = index.set_levels(pd.to_datetime(level), level=i)
                forecast.index = index
            else:
                forecast.index = pd.to_datetime(forecast.index)

            forecast.sort_index(inplace=True)

        self._forecast: Dict[Hashable, pd.Series]
        if isinstance(forecast, pd.Series):
            self._forecast = {forecast.name: forecast.dropna()}
        elif isinstance(forecast, pd.DataFrame):
            self._forecast = {col: forecast[col].dropna() for col in forecast.columns}
        elif forecast is None:
            self._forecast = {
                key: data.copy(deep=True) for key, data in self._actual.items()
            }
        else:
            raise ValueError(f"Incompatible type {type(forecast)} for 'forecast'.")

        self._fill_method = fill_method

    def zones(self) -> List:
        """Returns a list of all zones, where actual data is available."""
        return list(self._actual.keys())

    def actual(self, dt: DatetimeLike, zone: Optional[str] = None) -> Any:
        """Retrieves actual data point of zone at given time.

        If queried timestamp is not available in the `actual` dataframe, the fill_method
        is used to determine the data point.

        Args:
            dt: Timestamp, at which the data is needed.
            zone: Optional zone for the data. Has to be provided if there is more than one
                zone specified in the data. Defaults to None.

        Raises:
            ValueError: If there is no available data at specified zone or time.
        """
        dt = pd.to_datetime(dt)
        zone_data = self._get_zone_data(self._actual, zone)

        # Mypy somehow has trouble with indexing in a dataframe with DatetimeIndex
        # <https://github.com/python/mypy/issues/2410>
        if self._fill_method == "ffill":
            # searchsorted with 'side' specified in sorted df always returns an int
            time_index: int = zone_data.index.searchsorted(dt, side="right") # type: ignore
            if time_index > 0:
                return zone_data.iloc[time_index - 1] # type: ignore
            else:
                raise ValueError(f"'{dt}' is too early to get data in zone '{zone}'.")
        else:
            time_index = zone_data.index.searchsorted(dt, side="left") # type: ignore
            try:
                return zone_data.iloc[time_index] # type: ignore
            except IndexError:
                raise ValueError(f"'{dt}' is too late to get data in zone '{zone}'.")

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
        - If frequency is not specified, all existing data in the window will be returned.
          If data is already in the right frequency, it is advised that the frequency is
          not specified as that causes some performance overhead due to resampling.
        - For various resampling methods, the actual value valid at `start_time` is used.
          So you have to make sure that there is a valid actual value.
        - If there is more than one zone present in the data, zone has to be specified.
          (Note that zone name must also appear in actual data.)
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
        start_time = pd.to_datetime(start_time)
        end_time = pd.to_datetime(end_time)
        forecast: pd.Series = self._get_forecast_data_source(start_time, zone)

        # Resample the data to get the data to specified frequency
        if frequency is not None:
            frequency = pd.tseries.frequencies.to_offset(frequency)
            if frequency is None:
                raise ValueError(f"Frequency '{frequency}' invalid.")

            forecast_in_freq: pd.Series = self._resample_to_frequency(
                forecast, start_time, end_time, frequency, resample_method
            )

            # Check if there are NaN values in the result
            if forecast_in_freq.hasnans:
                raise ValueError(
                    f"Not enough data for frequency '{frequency}'"
                    f"with resample_method '{resample_method}'."
                )
            return forecast_in_freq

        start_index = forecast.index.searchsorted(start_time, side='right')
        return forecast.loc[forecast.index[start_index]:end_time] # type: ignore

    def _get_forecast_data_source(
        self, start_time: datetime, zone: Optional[str]
    ) -> pd.Series:
        """Returns series of zone data used to derive forecast prediction."""
        data_src = self._get_zone_data(self._forecast, zone)

        if data_src.index.nlevels > 1:
            # Forecast does include request timestamp
            try:
                # Get forecasts of the nearest existing timestamp lower than start time
                req_time = data_src[:start_time].index.get_level_values(0)[-1] # type: ignore
            except IndexError:
                raise ValueError(f"No forecasts available at time {start_time}.")
            data_src = data_src.loc[req_time]

        return data_src

    def _get_zone_data(
        self, data: Dict[Hashable, pd.Series], zone: Optional[str]
    ) -> pd.Series:
        """Return data of zone to be used.

        If zone is not specified, but there is only one zone available, the
        data of that zone is returned.

        Raises:
            ValueError: If zone can not be determined.
        """
        if zone is None:
            if len(data.keys()) == 1:
                zone_name = next(iter(data))
            else:
                raise ValueError("Zone needs to be specified.")
        elif zone in data.keys():
            zone_name = zone
        else:
            raise ValueError(f"Cannot retrieve data for zone '{zone}'.")

        return data[zone_name]

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
                cutoff_time = df.index[df.index.searchsorted(end_time, side='right')]
                df = df.loc[start_time:cutoff_time] # type: ignore
            except IndexError:
                df = df.loc[start_time:] # type: ignore
            # Add NaN values in the specified frequency
            combined_index = df.index.union(new_index, sort=True)
            df = df.reindex(combined_index)

            # Use specific resample method if specified to fill NaN values
            if resample_method == "bfill":
                df.bfill(inplace=True)
            elif resample_method is not None:
                # Add actual value to front of series because needed for interpolation
                df[start_time] = self.actual(start_time, zone=str(df.name))
                if resample_method == "ffill":
                    df.ffill(inplace=True)
                else:
                    df.interpolate(method=resample_method, inplace=True) # type: ignore

        # Get the data to the desired frequency after interpolation
        return df.reindex(new_index[1:]) # type: ignore

    def next_update(self, dt: DatetimeLike, zone: Optional[str] = None) -> datetime:
        """Returns the next time of when the actual trace will change.

        This method is being called in the time-based simulation model for Mosaik.
        """
        zone_data = self._get_zone_data(self._actual, zone)
        current_index = zone_data.index.asof(dt)
        next_iloc = zone_data.index.get_loc(current_index) + 1
        return zone_data.index[next_iloc]
