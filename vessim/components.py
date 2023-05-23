from datetime import datetime
from typing import Union, List
import pandas as pd

Time = Union[int, float, str, datetime]


class CarbonIntensityAPI:
    def __init__(self, data: pd.DataFrame):
        """Service for querying the carbon intensity at different times and locations.

        Args:
            data: DataFrame with carbon intensity values. Each index represents a
                timestamp and each column a location.
        """
        self.data = data

    def zones(self) -> List:
        """Returns a list of all available zones"""
        return list(self.data.columns)

    def carbon_intensity_at(self, now: Time, zone: str):
        """Returns the carbon intensity at a given time and zone.

        If the queried timestamp is not available in the `data` dataframe, the last valid
        datapoint is being returned.
        """
        try:
            location_carbon_intensity = self.data[zone]
        except KeyError:
            raise ValueError(f"Cannot retrieve carbon intensity at zone '{zone}'.")
        try:
            return location_carbon_intensity.loc[self.data.index.asof(now)]
        except KeyError:
            raise ValueError(f"Cannot retrieve carbon intensity at {now} in zone "
                             f"'{zone}'.")

