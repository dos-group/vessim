from datetime import datetime, timedelta
from typing import Union

import pandas as pd


Time = Union[int, float, str, datetime]


class Clock:
    def __init__(self, sim_start: Union[str, datetime]):
        self.sim_start = pd.to_datetime(sim_start)

    def to_datetime(self, simtime: int) -> datetime:
        return self.sim_start + timedelta(seconds=simtime)

    def to_simtime(self, dt: datetime) -> int:
        return (dt - self.sim_start).seconds


class TraceSimulator:

    def __init__(self, data: Union[pd.Series, pd.DataFrame]):
        self.data = data

    def next_update(self, dt: Time):
        current_index = self.data.index.asof(dt)
        next_iloc = self.data.index.get_loc(current_index) + 1
        return self.data.index[next_iloc]
