from collections import defaultdict
from datetime import datetime
from typing import Dict, Callable, Any

import pandas as pd

from vessim import TimeSeriesApi
from vessim.cosim._util import Clock, VessimSimulator, VessimModel, simplify_inputs


class Ecovisor:

    def __init__(self):
        self.data: Dict = defaultdict(dict)
        self.monitor_fns = []
        self.grid_signals = None
        self.zone = None
        self._clock = None

    def start(self, sim_start: datetime, grid_signals: Dict[str, TimeSeriesApi], zone: str):
        self.grid_signals = grid_signals
        self.zone = zone
        self._clock = Clock(sim_start)

    def add_monitor_fn(self, fn: Callable[[], Dict[str, Any]]):
        self.monitor_fns.append(fn)

    def step(self, time: int, inputs: Dict) -> None:
        self._monitor(time, inputs)
        # TODO here goes all code for the Cacu and SiL stuff
        #  this code can make use of all <inputs> and self.grid_signals

    def _monitor(self, time: int, inputs: Dict):
        inputs = simplify_inputs(inputs)
        dt = self._clock.to_datetime(time)

        for monitor_fn in self.monitor_fns:
            inputs.update(monitor_fn())

        for attr, value in inputs.items():
            self.data[attr][dt] = value

    def monitor_to_csv(self, out_path: str):
        pd.DataFrame(self.data).to_csv(out_path)


class EcovisorSim(VessimSimulator):

    META = {
        "type": "time-based",  # TODO maybe we should make this hybrid and let users decide
        "models": {
            "EcovisorModel": {
                "public": True,
                "any_inputs": True,
                "params": ["ecovisor"],
                "attrs": [],
            },
        },
    }

    def __init__(self) -> None:
        """Simple data collector for printing data at the end of simulation."""
        self.step_size = None
        super().__init__(self.META, _EcovisorModel)

    def init(self, sid, time_resolution, step_size: int, eid_prefix=None):
        self.step_size = step_size  # type: ignore
        return super().init(sid, time_resolution, eid_prefix=eid_prefix)

    def next_step(self, time):
        return time + self.step_size


class _EcovisorModel(VessimModel):
    def __init__(self, ecovisor: Ecovisor):
        self.ecovisor = ecovisor

    def step(self, time: int, inputs: Dict) -> None:
        self.ecovisor.step(time, inputs)
        # TODO here we need to set all properties that other entities should
        #   have access to in the simulation (if there are any)
