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

            2020-01-01 00:00:00     100     800     700
            2020-01-01 01:00:00     110     850     720
            2020-01-01 02:00:00     105     820     710
            2020-01-01 03:00:00     108     840     730
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
            (index1, sorted)      (index2)

            2020-01-01 00:00:00   2020-01-01 00:05:00   115    850    710
            ...
            2020-01-01 00:00:00   2020-01-01 00:55:00   110    870 	  720

            2020-01-01 01:00:00   2020-01-01 01:05:00   110    830    715
            ...
            2020-01-01 01:00:00   2020-01-01 01:55:00   120    870 	  740
            ------------------------------------------------------------------------
    """

    def __init__(
        self,
        actual: Union[pd.Series, pd.DataFrame],
        forecast: Optional[pd.DataFrame] = None,
    ):
        self.actual = actual if isinstance(actual, pd.DataFrame) else actual.to_frame()
        self.forecast = forecast

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
        start_time: Time,
        end_time: Time,
        zone: Optional[str] = None,
        frequency: Optional[Union[str, pd.DateOffset, timedelta]] = None,  # issue #140
        resampling_method: Optional[str] = None,
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
            resampling_method: Optional method, to deal with holes in resampled data.
                Can be either 'bfill', 'ffill' or an interpolation method.
                https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.interpolate.html#pandas.DataFrame.interpolate)

        Returns:
            pd.Series of forecasted data with timestamps of forecast as index.
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
            data_src = self.actual.loc[self.actual.index.asof(start_time):]
        else:
            # Get all data points corresponding to the nearest existing timestamp
            # of first index lower than start time
            first_index = self.forecast.index.get_level_values(0)
            data_src = self.forecast.loc[
                first_index[first_index <= start_time].max()
            ]

        if data_src.empty:
            raise ValueError(f"Cannot retrieve forecast data at '{start_time}'.")

        # Get data of specified zone and convert to pd.Series
        try:
            zone_data: pd.Series = data_src[[zone]].squeeze()
        except KeyError:
            raise ValueError(f"Cannot retrieve forecast data for zone '{zone}'.")

        # Cutoff the data at specified time window
        sampled_data: pd.Series = zone_data[zone_data.index <= end_time]

        # Resample the data to get the data to specified frequency
        if frequency is not None:
            frequency = pd.tseries.frequencies.to_offset(frequency)
            sampled_data = sampled_data.asfreq(frequency)

            # Use specific resampling method if specified to fill NaN values
            if resampling_method == "ffill":
                sampled_data.ffill(inplace=True)
            elif resampling_method == "bfill":
                sampled_data.bfill(inplace=True)
            elif resampling_method is not None:
                sampled_data.interpolate(method=resampling_method, inplace=True)

        return sampled_data

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
