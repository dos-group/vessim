from collections import defaultdict
from datetime import datetime
from typing import Dict, Callable, Any, Tuple

import pandas as pd

from vessim import TimeSeriesApi
from vessim.cosim._util import Clock, VessimSimulator, VessimModel


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
        p_delta, actors = _parse_controller_inputs(inputs)
        self.monitor(time, p_delta, actors)
        self.step(time, p_delta, actors)

    def monitor(self, time: int, p_delta: float, actors: Dict):
        dt = self._clock.to_datetime(time)
        self.monitor_log[dt] = dict(
            p_delta=p_delta,
            actors=actors,
        )
        for monitor_fn in self.custom_monitor_fns:
            self.monitor_log[dt].update(monitor_fn())

    def step(self, time: int, p_delta: float, actors: Dict):
        pass  # TODO

    def monitor_to_csv(self, out_path: str):
        # TODO this should translate data into CSV format
        pd.DataFrame(self.monitor_log).to_csv(out_path)


def _parse_controller_inputs(inputs: Dict[str, Dict[str, Any]]) -> Tuple[float, Dict]:
    p_delta = _get_val(inputs, "p_delta")
    actor_keys = [k for k in inputs.keys() if k.startswith("actor")]
    actors = defaultdict(dict)
    for k in actor_keys:
        _, actor_name, attr = k.split("/")
        actors[actor_name][attr] = _get_val(inputs, k)
    return p_delta, dict(actors)


def _get_val(inputs: Dict[str, Dict[str, Any]], key: str) -> Any:
    return list(inputs[key].values())[0]


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

    def init(self, sid, time_resolution, step_size: int):
        self.step_size = step_size  # type: ignore
        return super().init(sid, time_resolution)

    def next_step(self, time):
        return time + self.step_size


class _ControllerModel(VessimModel):
    def __init__(self, controller: Controller):
        self.controller = controller

    def step(self, time: int, inputs: Dict) -> None:
        self.controller.monitor_and_step(time, inputs)
        # TODO here we need to set all properties that other entities should
        #   have access to in the simulation (if there are any)
