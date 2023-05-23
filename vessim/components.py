from datetime import datetime
from typing import Union, List
import pandas as pd

Time = Union[int, float, str, datetime]


class CarbonIntensityApi:
    def __init__(self, data: pd.DataFrame, unit: str = "g_per_kWh"):
        """Service for querying the carbon intensity at different times and locations.

        Args:
            data: DataFrame with carbon intensity values. Each index represents a
                timestamp and each column a location.
            unit: Unit of the carbon intensity data: gCO2/kWh (`g_per_kWh`) or lb/MWh
                (`lb_per_MWh`). Note that Vessim internally assumes gCO2/kWh, so choosing
                lb/MWh will simply convert this data to gCO2/kWh.
        """
        self.data = data
        if unit == "lb_per_MWh":
            self.data = self.data * 0.45359237
        elif unit != "g_per_kWh":
            raise ValueError(f"Carbin intensity unit '{unit}' is not supported.")

    def zones(self) -> List:
        """Returns a list of all available zones."""
        return list(self.data.columns)

    def carbon_intensity_at(self, dt: Time, zone: str) -> float:
        """Returns the carbon intensity at a given time and zone.

        If the queried timestamp is not available in the `data` dataframe, the last valid
        datapoint is being returned.
        """
        try:
            zone_carbon_intensity = self.data[zone]
        except KeyError:
            raise ValueError(f"Cannot retrieve carbon intensity at zone '{zone}'.")
        try:
            return zone_carbon_intensity.loc[self.data.index.asof(dt)]
        except KeyError:
            raise ValueError(f"Cannot retrieve carbon intensity at {dt} in zone "
                             f"'{zone}'.")

