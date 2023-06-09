from datetime import datetime
from typing import Union, List

import pandas as pd

from vessim._util import Clock
from vessim.core import VessimSimulator, VessimModel

Time = Union[int, float, str, datetime]


class CarbonApi:
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
            raise ValueError(f"Carbon intensity unit '{unit}' is not supported.")

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

    def next_update(self, dt: Time):
        """Returns the next time of when the carbon intensity will change.

        This method is being called in the time-based simulation model for Mosaik.
        """
        current_index = self.data.index.asof(dt)
        next_iloc = self.data.index.get_loc(current_index) + 1
        return self.data.iloc[next_iloc].name


class CarbonApiSim(VessimSimulator):

    META = {
        'type': 'time-based',
        'models': {
            'CarbonApi': {
                'public': True,
                'params': ['zone'],
                'attrs': ['carbon_intensity'],
            },
        },
    }

    def __init__(self, ):
        super().__init__(self.META, CarbonApiModel)
        self.clock = None
        self.sim_start = None
        self.carbon_api = None

    def init(self, sid, time_resolution, sim_start: datetime, carbon_api: CarbonApi,
             eid_prefix=None):
        super().init(sid, time_resolution, eid_prefix=eid_prefix)
        self.clock = Clock(sim_start)
        self.carbon_api = carbon_api
        return self.meta

    def create(self, num, model, zone: str):
        return super().create(num, model, zone=zone, clock=self.clock,
                              carbon_api=self.carbon_api)

    def next_step(self, time: int) -> int:
        dt = self.clock.to_datetime(time)
        next_dt = self.carbon_api.next_update(dt)
        return self.clock.to_simtime(next_dt)


class CarbonApiModel(VessimModel):
    def __init__(self, carbon_api: CarbonApi, clock: Clock, zone: str):
        self.api = carbon_api
        self.clock = clock
        self.zone = zone
        self.carbon_intensity = None

    def step(self, time: int, inputs: dict) -> None:
        dt = self.clock.to_datetime(time)
        self.carbon_intensity = self.api.carbon_intensity_at(dt, self.zone)
