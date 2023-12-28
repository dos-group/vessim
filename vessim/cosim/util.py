import sys
from datetime import datetime, timedelta
from typing import Union

import mosaik_api  # type: ignore
import pandas as pd
from loguru import logger


class Clock:
    def __init__(self, sim_start: Union[str, datetime]):
        self.sim_start = pd.to_datetime(sim_start)

    def to_datetime(self, simtime: int) -> datetime:
        return self.sim_start + timedelta(seconds=simtime)

    def to_simtime(self, dt: datetime) -> int:
        return int((dt - self.sim_start).total_seconds())


def disable_mosaik_warnings(behind_threshold: float):  # TODO do we still need this since there is rt_strict?
    """Disables Mosaik's incorrect Loguru warnings.

    Mosaik currently deems specific attribute connections as incorrect and logs
    them as warnings. Also the simulation is always behind by a few fractions
    of a second (which is fine, code needs time to execute) which Mosaik also
    logs as a Warning. These Warnings are flagged as bugs in Mosaik's current
    developement and should be fixed within its next release. Until then, this
    function should do.

    Args:
        behind_threshold: Time the simulation is allowed to be behind schedule.
    """
    # Define a function to filter out WARNING level logs
    def filter_record(record):
        is_warning = record["level"].name == "WARNING"
        is_mosaik_log = record["name"].startswith("mosaik")
        is_attribute = record["function"] == "_check_attributes_values"
        is_below_threshold = (
            record["function"] == "rt_check" and
            float(record["message"].split(' - ')[1].split('s')[0]) < behind_threshold
        )
        return not (is_warning and is_mosaik_log and (is_below_threshold or is_attribute))

    # Add the filter to the logger
    logger.remove()
    logger.add(sys.stdout, filter=filter_record)
