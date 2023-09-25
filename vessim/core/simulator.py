from abc import ABC
from datetime import datetime
from typing import Union, List, Optional
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
            (index1)              (index2)

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
        forecast: Optional[pd.DataFrame] = None
    ):
        if isinstance(actual, pd.Series):
                actual = actual.to_frame()

        self.actual = actual
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

    def actual_at(self, dt: Time, zone: Optional[str] = None) -> float:
        """Retrieves actual data point of zone at given time.

        If queried timestamp is not available in the `actual` dataframe, the last valid
        datapoint is being returned.

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
            raise ValueError(f"Cannot retrieve actual data at {dt} in zone {zone}.")

    def forecast_at(
        self, dt: Time, end: Time, frequency: int, zone: Optional[str] = None
    ) -> pd.Series:
        """Retrieves `frequency` number of forecasted data points within window.

        If no forecast time-series data is provided, actual data is used.

        Args:
            dt: Starting time of the window.
            end: End time of the window.
            frequency: Number of data points to be generated within the window.
            zone: Geographical zone of the forecast. Defaults to the first zone of
                the dataset.
        """
        if zone is None:
            if len(self.zones()) == 1:
                zone = self.zones()[0]
            else:
                raise ValueError("Zone needs to be specified.")

        # Determine which data source to use
        if self.forecast is None:
            data_source = self.actual
        else:
            data_source = self.forecast.loc[dt]

        # Get data of specified zone
        try:
            zone_data = data_source[zone]
        except KeyError:
            raise ValueError(f"Cannot retrieve forecast data for zone '{zone}'.")

        # Filter the data within the specified window
        filtered_data = zone_data.loc[dt:end]

        # Resample the data to get the desired number of points
        if len(filtered_data) > frequency:
            resampled_data = filtered_data.sample(n=frequency)
            return resampled_data.sort_index()
        else:
            raise ValueError(f"Not enough data provided for frequency {frequency}.")

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
        actual: pd.DataFrame,
        forecast: Optional[pd.DataFrame] = None,
        unit: str = "g_per_kWh"
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
