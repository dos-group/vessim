from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime
from typing import Any, MutableMapping, Optional, Callable

import mosaik_api_v3  # type: ignore
import pandas as pd

from vessim.signal import Signal


class Controller(ABC):
    def __init__(self, step_size: Optional[int] = None):
        self.step_size = step_size

    def start(self):
        """Function to be executed before simulation is started."""
        pass

    @abstractmethod
    def step(
        self, time: datetime, p_delta: float, actor_states: dict, storage_state: Optional[dict]
    ) -> None:
        """Performs a simulation step.

        Args:
            time: Current datetime.
            p_delta: Current power delta from the microgrid after the storage has been
                (de)charged. If negative, this power must be drawn from the public grid.
                If positive, the power can be fed to the public grid or must be curtailed.
            actor_states: Contains the last state dictionaries by all actors in the
                microgrid. The state dictionary is defined by the actor and can contain
                any information about the actor's state.
            storage_state: Contains the last state dictionary of the storage instance if
                microgrid has a storage and None otherwise. The state dictionary is defined
                by the storage and can contain any information about the storage state.
        """

    def finalize(self) -> None:
        """This method can be overridden clean-up after the simulation finished."""
        pass


class Monitor(Controller):
    def __init__(
        self,
        step_size: Optional[int] = None,
        grid_signals: Optional[dict[str, Signal]] = None,
    ):
        super().__init__(step_size=step_size)
        self.grid_signals = grid_signals if grid_signals is not None else {}
        self.monitor_log: dict[datetime, dict] = defaultdict(dict)
        self.custom_monitor_fns: list[Callable] = []

        for signal_name, signal_api in self.grid_signals.items():

            def fn(time):
                return {signal_name: signal_api.at(time)}

            self.add_monitor_fn(fn)

    def add_monitor_fn(self, fn: Callable[[float], dict[str, Any]]):
        self.custom_monitor_fns.append(fn)

    def step(
        self, time: datetime, p_delta: float, actor_states: dict, storage_state: Optional[dict]
    ) -> None:
        log_entry = dict(
            p_delta=p_delta,
            actor_states=actor_states,
        )
        if storage_state is not None:
            log_entry["storage_state"] = storage_state
        for monitor_fn in self.custom_monitor_fns:
            log_entry.update(monitor_fn(time))
        self.monitor_log[time] = log_entry

    def to_csv(self, out_path: str):
        df = pd.DataFrame({k: _flatten_dict(v) for k, v in self.monitor_log.items()}).T
        df.to_csv(out_path)


def _flatten_dict(d: MutableMapping, parent_key: str = "") -> MutableMapping:
    items: list[tuple[str, Any]] = []
    for k, v in d.items():
        new_key = parent_key + "." + k if parent_key else k
        if isinstance(v, MutableMapping):
            items.extend(_flatten_dict(v, str(new_key)).items())
        else:
            items.append((new_key, v))
    return dict(items)


class _ControllerSim(mosaik_api_v3.Simulator):
    META = {
        "type": "time-based",
        "models": {
            "Controller": {
                "public": True,
                "any_inputs": True,
                "params": ["controller"],
                "attrs": [],
            },
        },
    }

    def __init__(self):
        super().__init__(self.META)
        self.eid = "Controller"
        self.step_size = None
        self.clock = None
        self.controller = None

    def init(self, sid, time_resolution=1.0, **sim_params):
        self.step_size = sim_params["step_size"]
        self.clock = sim_params["clock"]
        return self.meta

    def create(self, num, model, **model_params):
        assert num == 1, "Only one instance per simulation is supported"
        self.controller = model_params["controller"]
        return [{"eid": self.eid, "type": model}]

    def step(self, time, inputs, max_advance):
        assert self.controller is not None
        now = self.clock.to_datetime(time)
        self.controller.step(now, *_parse_controller_inputs(inputs[self.eid]))
        return time + self.step_size

    def get_data(self, outputs):
        return {}  # TODO so far unused

    def finalize(self) -> None:
        """Stops the api server and the collector thread when the simulation finishes."""
        assert self.controller is not None
        self.controller.finalize()


def _parse_controller_inputs(
    inputs: dict[str, dict[str, Any]],
) -> tuple[float, dict, Optional[dict]]:
    p_delta = _get_val(inputs, "p_delta")
    actor_keys = [k for k in inputs.keys() if k.startswith("actor")]
    actors: defaultdict[str, Any] = defaultdict(dict)
    for k in actor_keys:
        _, actor_name = k.split(".")
        actors[actor_name] = _get_val(inputs, k)
    if "storage_state" in inputs.keys():
        storage_state = _get_val(inputs, "storage_state")
    else:
        storage_state = None
    assert p_delta is not None
    return p_delta, dict(actors), storage_state


def _get_val(inputs: dict, key: str) -> Any:
    return list(inputs[key].values())[0]
