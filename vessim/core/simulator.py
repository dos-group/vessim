from abc import ABC
from datetime import datetime, timedelta
from typing import Union, List, Optional, Any
import numpy as np

import pandas as pd

Time = Union[int, float, str, datetime]


class TraceSimulator(ABC):
    """Base class for integrating time-series data into simulation.

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
        forecast: Optional[pd.DataFrame] = None,
    ):
        self.actual = actual if isinstance(actual, pd.DataFrame) else actual.to_frame()
        self.actual.sort_index()
        self.forecast = forecast
        if self.forecast is not None:
            self.forecast.sort_index()

    def zones(self) -> List:
        """Returns a list of all available zones."""
        return list(self.actual.columns)

    def apply_error(
        self, error: float, target: str = "actual", seed: Optional[int] = None
    ) -> None:
        """Apply random noise to specified dataframe (actual or forecast).

        Derived from https://github.com/dos-group/lets-wait-awhile/blob/master/simulate.py

        Args:
            error: The magnitude of the error to apply.
            target: The dataframe to apply error to, either "actual" or "forecast".
                Defaults to "actual".
            seed: The random seed for reproducibility. Defaults to None.

        Raises:
            ValueError: If the specified target is neither "actual" nor "forecast".
        """
        rng = np.random.default_rng(seed)

        if target == "actual":
            self.actual += rng.normal(
                0, error * self.actual.mean(), size=self.actual.shape
            )
        elif target == "forecast":
            if self.forecast is None:
                raise ValueError("Forecast data is not provided.")
            self.forecast += rng.normal(
                0, error * self.forecast.mean(), size=self.forecast.shape
            )
        else:
            raise ValueError(
                f"Invalid target: {target}. Target should be  'actual' or 'forecast'."
            )

    def actual_at(self, dt: Time, zone: Optional[str] = None) -> Any:
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
            zone_actual = self.actual[zone]
        except KeyError:
            raise ValueError(f"Cannot retrieve actual data at zone '{zone}'.")
        try:
            return zone_actual.loc[self.actual.index.asof(dt)]
        except KeyError:
            raise ValueError(f"Cannot retrieve actual data at '{dt}' in zone '{zone}'.")

    def forecast_at(
        self,
        start_time: datetime,
        end_time: datetime,
        zone: Optional[str] = None,
        frequency: Optional[Union[str, pd.DateOffset, timedelta]] = None,  # issue #140
        resample_method: Optional[str] = None,
    ) -> pd.Series:
        """Retrieves of forecasted data points within window at a frequency.

        - If no forecast time-series data is provided, actual data is used.
        - Specified timestamps are always rounded down to the nearest existing.
        - If there is more than one zone present in the data, zone has to be specified.
        - If frequency is not specified, all existing data in the window will be returned.

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
                resample_method="linear",
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
        if self.forecast is None:
            # Get all data points beginning at the nearest existing timestamp
            # lower than start time from actual data
            data_src = self.actual.loc[self.actual.index.asof(start_time) :]
        else:
            # Get the nearest existing timestamp lower than start time from forecasts
            first_index = self.forecast.index.get_level_values(0)
            request_time = first_index[first_index <= start_time].max()

            # Retrieve the actual value at the time and attach it to the front of the
            # forecast data with the timestamp (for interpolation at a later stage)
            actual_value = self.actual.loc[self.actual.index.asof(request_time)]
            actual_value.name = request_time
            data_src = pd.concat(
                [actual_value.to_frame().T, self.forecast.loc[request_time]]
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

    def next_update(self, dt: Time) -> datetime:
        """Returns the next time of when the trace will change.

        This method is being called in the time-based simulation model for Mosaik.
        """
        current_index = self.actual.index.asof(dt)
        next_iloc = self.actual.index.get_loc(current_index) + 1
        return self.actual.index[next_iloc]


class CarbonApi(TraceSimulator):
    """Service for querying the carbon intensity at different times and locations.

    Args:
        actual: Time-series data for actual carbon intensity in specific zones.
            Details on format can be found in the TraceSimulator class.
        forecast: Time-series data for forecasted carbon intensity in specific zones.
            Details on format can be found in the TraceSimulator class.
        unit: Unit of the carbon intensity data: gCO2/kWh (`g_per_kWh`) or lb/MWh
            (`lb_per_MWh`). Note that Vessim internally assumes gCO2/kWh, so choosing
            lb/MWh will simply convert this data to gCO2/kWh.
    """

    def __init__(
        self,
        actual: Union[pd.Series, pd.DataFrame],
        forecast: Optional[pd.DataFrame] = None,
        unit: str = "g_per_kWh",
    ):
        super().__init__(actual, forecast)
        if unit == "lb_per_MWh":
            self.actual = self.actual * 0.45359237
            if self.forecast is not None:
                self.forecast = self.forecast * 0.45359237
        elif unit != "g_per_kWh":
            raise ValueError(f"Carbon intensity unit '{unit}' is not supported.")

    def carbon_intensity_at(self, dt: Time, zone: Optional[str] = None) -> float:
        """Returns the carbon intensity at a given time and zone.

        Raises:
            ValueError: If there is no available data at apecified zone or time.
        """
        return self.actual_at(dt, zone)


class Generator(TraceSimulator):
    def power_at(self, dt: Time, zone: Optional[str] = None) -> float:
        """Returns the power generated at a given time.

        If the queried timestamp is not available in the `data` dataframe, the last valid
        datapoint is being returned.

        Raises:
            ValueError: If there is no available data at apecified zone or time.
        """
        return self.actual_at(dt, zone)
