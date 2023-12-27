from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime
from typing import Dict, Callable, Any, Tuple, TYPE_CHECKING, MutableMapping

import pandas as pd

from vessim.cosim._util import Clock, VessimSimulator, VessimModel

if TYPE_CHECKING:
    from vessim.core.microgrid import Microgrid


class Controller(ABC):

    def __init__(self, step_size: int):
        self.step_size = step_size

    @abstractmethod
    def start(self, microgrid: "Microgrid", sim_start: datetime, grid_signals: Dict):
        pass  # TODO document

    @abstractmethod
    def step(self, time: int, p_delta: float, actors: Dict) -> None:
        pass  # TODO document


class Monitor(Controller):

    def __init__(self, step_size: int, monitor_storage=True, monitor_grid_signals=True):
        super().__init__(step_size)
        self.monitor_storage = monitor_storage
        self.monitor_grid_signals = monitor_grid_signals
        self.monitor_log: Dict[datetime, Dict] = defaultdict(dict)
        self.custom_monitor_fns = []

        self.microgrid = None
        self.clock = None
        self.grid_signals = None

    def start(self, microgrid: "Microgrid", sim_start: datetime, grid_signals: Dict):
        self.microgrid = microgrid  # TODO unused in monitor but used in cacu
        self.grid_signals = grid_signals  # TODO unused in monitor but used in cacu
        self.clock = Clock(sim_start)
        if self.monitor_storage:
            self.add_monitor_fn(lambda time: {"storage": microgrid.storage.info()})
        if self.monitor_grid_signals:
            for signal_name, signal_api in grid_signals.items():
                self.add_monitor_fn(lambda time: {
                    signal_name: grid_signals[signal_name].actual(self.clock.to_datetime(time))
                })

    def add_monitor_fn(self, fn: Callable[[float], Dict[str, Any]]):
        self.custom_monitor_fns.append(fn)

    def step(self, time: int, p_delta: float, actors: Dict) -> None:
        self.monitor(time, p_delta, actors)

    def monitor(self, time: int, p_delta: float, actors: Dict) -> None:
        log_entry = dict(
            p_delta=p_delta,
            actors=actors,
        )
        for monitor_fn in self.custom_monitor_fns:
            log_entry.update(monitor_fn(time))
        self.monitor_log[self.clock.to_datetime(time)] = log_entry

    def monitor_log_to_csv(self, out_path: str):
        df = pd.DataFrame({k: flatten_dict(v) for k, v in self.monitor_log.items()}).T
        df.to_csv(out_path)


def flatten_dict(d: MutableMapping, parent_key: str = '') -> MutableMapping:
    items = []
    for k, v in d.items():
        new_key = parent_key + "." + k if parent_key else k
        if isinstance(v, MutableMapping):
            items.extend(flatten_dict(v, str(new_key)).items())
        else:
            items.append((new_key, v))
    return dict(items)


class ControllerSim(VessimSimulator):

    META = {
        "type": "time-based",
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
        self.controller.step(time, *_parse_controller_inputs(inputs))


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
