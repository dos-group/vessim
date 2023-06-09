from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Callable, Any

import pandas as pd
import csv
from loguru import logger

import mosaik_api

from vessim._util import Clock

META = {
    "type": "event-based",
    "models": {
        "Monitor": {
            "public": True,
            "any_inputs": True,
            "params": ["fn", "sim_start"],
            "attrs": [],
        },
    },
}


class Monitor(mosaik_api.Simulator):
    """Simple data collector for printing data at the end of simulation.

    Attributes:
        eid: Identifier of Simulator Instance
        data: Dictionary for holding the necessary simulation data
    """

    def __init__(self):
        super().__init__(META)
        self.eid = None
        self.data = defaultdict(dict)
        self.fn = None
        self._clock = None

    def init(self, sid, time_resolution):
        return self.meta

    def create(self, num, model, fn: Callable[[], Dict[str, Any]], sim_start: datetime):
        self.fn = fn
        self._clock = Clock(sim_start)
        if num > 1 or self.eid is not None:
            raise RuntimeError("Can only create one instance of Monitor.")

        self.eid = "Monitor"
        return [{"eid": self.eid, "type": model}]

    def step(self, time, inputs, max_advance):
        dt = self._clock.to_datetime(time)
        data = inputs.get(self.eid, {})
        logger.info(f"# --- {str(dt):>5} ---")
        for attr, values in data.items():
            for src, value in values.items():
                logger.info(f"{attr}: {value}")
                self.data[attr][dt] = value
        if self.fn is not None:
            for attr, value in self.fn().items():
                logger.info(f"{attr}: {value}")
                self.data[attr][dt] = value
        return None

    def finalize(self):
        """Collected data is printed to file at simulation end."""
        pd.DataFrame(self.data).to_csv("data.csv")
