from collections import defaultdict
from datetime import datetime
from typing import Dict, Callable, Any, List

import pandas as pd

from vessim import TimeSeriesApi
from vessim.cosim._util import Clock, VessimSimulator, VessimModel, simplify_inputs


class Controller:

    def __init__(self):
        self.monitor_log: Dict[datetime, Dict] = defaultdict(dict)
        self.custom_monitor_fns = []

        self.grid_signals = None
        self.zone = None
        self._clock = None

    def start(self, sim_start: datetime, grid_signals: Dict[str, TimeSeriesApi], zone: str):
        self.grid_signals = grid_signals
        self.zone = zone
        self._clock = Clock(sim_start)

    def add_custom_monitor_fn(self, fn: Callable[[], Dict[str, Any]]):
        self.custom_monitor_fns.append(fn)

    def monitor_and_step(self, time: int, inputs: Dict) -> None:
        self.monitor(time, inputs)
        self.step(time, inputs)

    def monitor(self, time: int, inputs: Dict):
        inputs = simplify_inputs(inputs)
        dt = self._clock.to_datetime(time)

        self.monitor_log[dt] = inputs

        for monitor_fn in self.custom_monitor_fns:
            inputs.update(monitor_fn())

        for attr, value in inputs.items():
            # TODO data should be a more generic format
            self.monitor_log[attr][dt] = value

    def step(self, time: int, inputs: Dict):
        pass  # TODO

    def monitor_to_csv(self, out_path: str):
        # TODO this should translate data into CSV format
        pd.DataFrame(self.monitor_log).to_csv(out_path)


class ControllerSim(VessimSimulator):

    META = {
        "type": "time-based",  # TODO maybe we should make this hybrid and let users decide
        "models": {
            "ControllerModel": {
                "public": True,
                "any_inputs": True,
                "params": ["controller"],
                "attrs": [],
            },
        },
    }

    def __init__(self) -> None:
        """Simple data collector for printing data at the end of simulation."""
        self.step_size = None
        super().__init__(self.META, _ControllerModel)

    def init(self, sid, time_resolution, step_size: int, eid_prefix=None):
        self.step_size = step_size  # type: ignore
        return super().init(sid, time_resolution, eid_prefix=eid_prefix)

    def next_step(self, time):
        return time + self.step_size


class _ControllerModel(VessimModel):
    def __init__(self, controller: Controller):
        self.controller = controller

    def step(self, time: int, inputs: Dict) -> None:
        self.controller.monitor_and_step(time, inputs)
        # TODO here we need to set all properties that other entities should
        #   have access to in the simulation (if there are any)
