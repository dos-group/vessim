from collections import defaultdict

import pandas as pd
import csv
from loguru import logger

import mosaik_api


META = {
    "type": "event-based",
    "models": {
        "Monitor": {
            "public": True,
            "any_inputs": True,
            "params": [],
            "attrs": [],
        },
    },
}


class Collector(mosaik_api.Simulator):
    """Simple data collector for printing data at the end of simulation.

    Attributes:
        eid: Identifier of Simulator Instance
        data: Dictionary for holding the necessary simulation data
    """

    def __init__(self):
        super().__init__(META)
        self.eid = None
        self.data = defaultdict(dict)

    def init(self, sid, time_resolution):
        return self.meta

    def create(self, num, model):
        if num > 1 or self.eid is not None:
            raise RuntimeError("Can only create one instance of Monitor.")

        self.eid = "Monitor"
        return [{"eid": self.eid, "type": model}]

    def step(self, time, inputs, max_advance):
        data = inputs.get(self.eid, {})
        logger.info(f"# {str(time):>5} ----------")
        for attr, values in data.items():
            for src, value in values.items():
                logger.info(f"{src}[{attr}] = {value}")
                self.data[attr][time] = value
        return None

    def finalize(self):
        """Collected data is printed to file at simulation end."""
        pd.DataFrame(self.data).to_csv("data.csv")
