from abc import ABC
from datetime import datetime
from typing import Union, List, Optional

import pandas as pd

Time = Union[int, float, str, datetime]


class TraceSimulator(ABC):

    def __init__(self, data: Union[pd.Series, pd.DataFrame]):
        self.data = data

    def next_update(self, dt: Time):
        """Returns the next time of when the trace will change.

        This method is being called in the time-based simulation model for Mosaik.
        """
        current_index = self.data.index.asof(dt)
        next_iloc = self.data.index.get_loc(current_index) + 1
        return self.data.index[next_iloc]


class CarbonApi(TraceSimulator):
    def __init__(self, data: pd.DataFrame, unit: str = "g_per_kWh"):
        """Service for querying the carbon intensity at different times and locations.

        Args:
            data: DataFrame with carbon intensity values. Each index represents a
                timestamp and each column a location.
            unit: Unit of the carbon intensity data: gCO2/kWh (`g_per_kWh`) or lb/MWh
                (`lb_per_MWh`). Note that Vessim internally assumes gCO2/kWh, so choosing
                lb/MWh will simply convert this data to gCO2/kWh.
        """
        super().__init__(data)
        if unit == "lb_per_MWh":
            self.data = self.data * 0.45359237
        elif unit != "g_per_kWh":
            raise ValueError(f"Carbon intensity unit '{unit}' is not supported.")

    def zones(self) -> List:
        """Returns a list of all available zones."""
        return list(self.data.columns)

    def carbon_intensity_at(self, dt: Time, zone: Optional[str] = None) -> float:
        """Returns the carbon intensity at a given time and zone.

        If the queried timestamp is not available in the `data` dataframe, the last valid
        datapoint is being returned.
        """
        if zone is None:
            if len(self.zones()) == 1:
                zone = self.zones()[0]
            else:
                raise ValueError("Need to specify carbon intensity zone.")
        try:
            zone_carbon_intensity = self.data[zone]
        except KeyError:
            raise ValueError(f"Cannot retrieve carbon intensity at zone '{zone}'.")
        try:
            return zone_carbon_intensity.loc[self.data.index.asof(dt)]
        except KeyError:
            raise ValueError(f"Cannot retrieve carbon intensity at {dt} in zone "
                             f"'{zone}'.")


class Generator(TraceSimulator):

    def power_at(self, dt: Time) -> float:
        """Returns the power generated at a given time.

        If the queried timestamp is not available in the `data` dataframe, the last valid
        datapoint is being returned.

        Raises:
            ValueError: If no datapoint is found for the given timestamp.
        """
        try:
            return self.data.loc[self.data.index.asof(dt)]
        except KeyError:
            raise ValueError(f"Cannot retrieve power at {dt}.")
