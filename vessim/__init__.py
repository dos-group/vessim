"""A simulator for carbon-aware applications and systems."""

from datetime import datetime, timedelta
from typing import Union, List, Optional, Any

import pandas as pd

DatetimeLike = Union[str, datetime]


class TimeSeriesApi:
    """Simulates an API for time series data like solar irradiance or carbon intensity.

    Args:
        actual: The actual time-series data to be used. It should follow this
            structure:
            ------------------------------------------------------------------------
            Timestamp (index)       Zone A  Zone B  Zone C

            2020-01-01T00:00:00     100     800     700
            2020-01-01T01:00:00     110     850     720
            2020-01-01T02:00:00     105     820     710
            2020-01-01T03:00:00     108     840     730
            ------------------------------------------------------------------------
            Note that while interpolation is possible when retrieving forecasts,
            `frontfill` is always used on the actual data if no data is present at the
            time. If you wish a different behavior, you have to change your actual data
            beforehand (e.g by resampling into a different frequency).
        forecast: An optional time-series dataset representing forecasted values.
            - If `forecast` is not provided, predictions are derived from the
            actual data.
            - It's assumed that the forecasted data is supplied with a reference
            timestamp, termed as "Request Timestamp."
            - Correspondingly, each row in the forecasted data will also have an
            associated "Forecast Timestamp" indicating the actual time of the
            forecasted data. For example:
            ------------------------------------------------------------------------
            Request Timestamp     Forecast Timestamp    Zone A Zone B Zone C
            (index1)              (index2)

            2020-01-01T00:00:00   2020-01-01T00:05:00   115    850    710
            ...
            2020-01-01T00:00:00   2020-01-01T00:55:00   110    870 	  720
            2020-01-01T00:00:00   2020-01-01T01:00:00   110    860 	  715
            2020-01-01T01:00:00   2020-01-01T01:05:00   110    830    715
            ...
            ------------------------------------------------------------------------
    """

    def __init__(
        self,
        actual: Union[pd.Series, pd.DataFrame],
        forecast: Optional[Union[pd.Series, pd.DataFrame]] = None,
    ):
        actual.sort_index()
        if isinstance(actual, pd.Series):
            self._actual = actual.to_frame()
        elif isinstance(actual, pd.DataFrame):
            self._actual = actual
        else:
            raise ValueError(f"Incompatible type {type(actual)} for 'actual'.")

        if isinstance(forecast, (pd.Series, pd.DataFrame)):
            forecast.sort_index()
            if isinstance(forecast, pd.Series):
                forecast = forecast.to_frame()
        self._forecast = forecast

    def zones(self) -> List:
        """Returns a list of all available zones."""
        return list(self._actual.columns)

    def actual(self, dt: DatetimeLike, zone: Optional[str] = None) -> Any:
        """Retrieves actual data point of zone at given time.

        If queried timestamp is not available in the `actual` dataframe, the last valid
        datapoint is being returned.

        Args:
            dt: Timestamp, at which the data is needed.
            zone: Optional Zone for the data. Has to be provided if there is more than one
                zone specified in the data. Defaults to None.

        Raises:
            ValueError: If there is no available data at apecified zone or time.
        """
        if zone is None:
            if len(self.zones()) == 1:
                zone = self.zones()[0]
            else:
                raise ValueError("Zone needs to be specified.")
        try:
            zone_actual = self._actual[zone]
        except KeyError:
            raise ValueError(f"Cannot retrieve actual data at zone '{zone}'.")
        try:
            return zone_actual.loc[self._actual.index.asof(dt)]
        except KeyError:
            raise ValueError(f"Cannot retrieve actual data at '{dt}' in zone '{zone}'.")

    def forecast(
        self,
        start_time: DatetimeLike,
        end_time: DatetimeLike,
        zone: Optional[str] = None,
        frequency: Optional[Union[str, pd.DateOffset, timedelta]] = None,  # issue #140
        resample_method: Optional[str] = None,
    ) -> pd.Series:
        """Retrieves of forecasted data points within window at a frequency.

        - If no forecast time-series data is provided, actual data is used.
        - Specified timestamps are always rounded down to the nearest existing.
        - If there is more than one zone present in the data, zone has to be specified.
        - If frequency is not specified, all existing data in the window will be returned.
        - For various resampling methods, the last actual value is used.

        Args:
            start_time: Starting time of the window.
            end_time: End time of the window.
            zone: Optional geographical zone of the forecast. Defaults to None.
            frequency: Optional interval, in which the forecast data is to be provided.
                Defaults to None.
            resample_method: Optional method, to deal with holes in resampled data.
                Can be either 'bfill', 'ffill' or an interpolation method.
                https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.interpolate.html#pandas.DataFrame.interpolate)

        Returns:
            pd.Series of forecasted data with timestamps of forecast as index.

        Raises:
            ValueError: If there is no available data at apecified zone or time, or
                there is not enough data for frequency, without resample_method specified.

        Example:
            With actual data like this:
            ------------------------------------------------------------------------
            Timestamp (index)       Zone A

            2020-01-01T00:00:00     4
            2020-01-01T01:00:00     6
            2020-01-01T02:00:00     2
            2020-01-01T03:00:00     8
            ------------------------------------------------------------------------
            And forecast data like this:
            ------------------------------------------------------------------------
            Request Timestamp     Forecast Timestamp    Zone A
            (index1)              (index2)

            2020-01-01T00:00:00   2020-01-01T01:00:00   5
            2020-01-01T00:00:00   2020-01-01T02:00:00   2
            2020-01-01T00:00:00   2020-01-01T03:00:00   6
            ------------------------------------------------------------------------
            The call forecast_at(
                start_time=pd.to_datetime("2020-01-01T00:00:00"),
                end_time=pd.to_datetime("2020-01-01T02:00:00"),
                frequency="30T",
                resample_method="time",
            )
            would return the following:
            ------------------------------------------------------------------------
            Forecast Timestamp (index)  Zone A

            2020-01-01T00:30:00         4.5
            2020-01-01T01:00:00         5
            2020-01-01T01:30:00         3.5
            2020-01-01T02:00:00         2
            ------------------------------------------------------------------------
        """
        if zone is None:
            if len(self.zones()) == 1:
                zone = self.zones()[0]
            else:
                raise ValueError("Zone needs to be specified.")

        # Determine which data source to use
        data_src: pd.DataFrame
        if self._forecast is None:
            # Get all data points beginning at the nearest existing timestamp
            # lower than start time from actual data
            data_src = self._actual.loc[self._actual.index.asof(start_time):]
        else:
            # Get the nearest existing timestamp lower than start time from forecasts
            first_index = self._forecast.index.get_level_values(0)
            request_time = first_index[first_index <= start_time].max()

            # Retrieve the actual value at the time and attach it to the front of the
            # forecast data with the timestamp (for interpolation at a later stage)
            actual_value = self._actual.loc[self._actual.index.asof(request_time)]
            data_src = pd.concat(
                [actual_value.to_frame().T, self._forecast.loc[request_time]]
            )

        if data_src.empty:
            raise ValueError(f"Cannot retrieve forecast data at '{start_time}'.")

        # Get data of specified zone and convert to pd.Series
        try:
            forecast: pd.Series = data_src[[zone]].squeeze()
        except KeyError:
            raise ValueError(f"Cannot retrieve forecast data for zone '{zone}'.")

        # Resample the data to get the data to specified frequency
        if frequency is not None:
            frequency = pd.tseries.frequencies.to_offset(frequency)
            if frequency is None:
                raise ValueError(f"Frequency '{frequency}' invalid." )

            # Add NaN values in the specified frequency
            new_index = pd.date_range(start=start_time, end=end_time, freq=frequency)
            combined_index = forecast.index.union(new_index).sort_values()
            forecast = forecast.reindex(combined_index)

            # Use specific resample method if specified to fill NaN values
            if resample_method == "ffill":
                forecast.ffill(inplace=True)
            elif resample_method == "bfill":
                forecast.bfill(inplace=True)
            elif resample_method is not None:
                forecast.interpolate(method=resample_method, inplace=True)  # type: ignore
            elif forecast.isnull().values.any(): # type: ignore
                # Check if there are NaN values if resample method is not specified
                raise ValueError(
                    f"Not enough data at frequency '{frequency}'. Specify resample_method"
                )

            # Get the data to the desired frequency after interpolation
            return (
                forecast.loc[
                    (forecast.index >= start_time) & (forecast.index <= end_time)
                ]
                .asfreq(frequency)
                .iloc[1:]
            )

        return forecast.loc[(forecast.index > start_time) & (forecast.index <= end_time)]

    def next_update(self, dt: DatetimeLike) -> datetime:
        """Returns the next time of when the trace will change.

        This method is being called in the time-based simulation model for Mosaik.
        """
        current_index = self._actual.index.asof(dt)
        next_iloc = self._actual.index.get_loc(current_index) + 1
        return self._actual.index[next_iloc]
