from __future__ import annotations

from datetime import datetime, timedelta
from typing import Union

import pandas as pd

DatetimeLike = Union[str, datetime]


class Clock:
    def __init__(self, sim_start: str | datetime):
        self.sim_start = pd.to_datetime(sim_start)

    def to_datetime(self, simtime: int) -> datetime:
        return self.sim_start + timedelta(seconds=simtime)

    def to_simtime(self, dt: datetime) -> int:
        return int((dt - self.sim_start).total_seconds())
