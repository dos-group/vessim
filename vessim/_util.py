from __future__ import annotations

from datetime import datetime, timedelta
from typing import Union
from loguru import logger
import sys

import pandas as pd
import numpy as np

DatetimeLike = Union[str, datetime, np.datetime64]


class Clock:
    def __init__(self, sim_start: str | datetime):
        self.sim_start = pd.to_datetime(sim_start)

    def to_datetime(self, simtime: int) -> datetime:
        return self.sim_start + timedelta(seconds=simtime)

    def to_simtime(self, dt: datetime) -> int:
        return int((dt - self.sim_start).total_seconds())


def disable_rt_warnings(behind_threshold: float):
    """Disables Mosaik's rt_check warnings.

    Mosaik's current implementation of the real-time checks are faulty and a new
    implementation is already outlined in
    https://gitlab.com/mosaik/mosaik/-/issues/172. As this issue was opened in
    June 2023, it is unlikely that the issue will be resolved soon. Therefore,
    we disable the warnings with a threshold after which these offsets are
    logged.

    Args:
        behind_threshold: Time the simulation is allowed to be behind schedule.
    """

    def filter_record(record):
        is_warning = record["level"].name == "WARNING"
        is_mosaik_log = record["name"].startswith("mosaik")
        is_below_threshold = (
            record["function"] == "rt_check"
            and float(record["message"].split(" - ")[1].split("s")[0]) < behind_threshold
        )
        return not (is_warning and is_mosaik_log and is_below_threshold)

    # Add the filter to the logger
    logger.remove()
    logger.add(sys.stdout, filter=filter_record)
