from datetime import datetime, timedelta
from typing import Union

import pandas as pd


class Clock:
    def __init__(self, sim_start: Union[str, datetime]):
        self.sim_start = pd.to_datetime(sim_start)

    def to_datetime(self, simtime: int) -> datetime:
        return self.sim_start + timedelta(seconds=simtime)

    def to_simtime(self, dt: datetime) -> int:
        return (dt - self.sim_start).seconds
