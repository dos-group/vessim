from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime
from typing import Any, TYPE_CHECKING, MutableMapping, Optional, Callable

import mosaik_api  # type: ignore
import pandas as pd

from vessim.util import Clock

if TYPE_CHECKING:
    from vessim.cosim import Microgrid


class Controller(ABC):
    def __init__(self, step_size: Optional[int] = None):
        self.step_size = step_size

    @abstractmethod
    def start(self, microgrid: Microgrid, clock: Clock, grid_signals: dict) -> None:
        """Supplies the controller with objects available after simulation start.

        Args:
            microgrid: The microgrid under control.
            clock: The clock of the simulation environment.
            grid_signals: All grid signals available in the simulation environment.
        """

    @abstractmethod
    def step(self, time: int, p_delta: float, actor_infos: dict) -> None:
        """Performs a simulation step.

        Args:
            time: Current simulation time.
            p_delta: Current power delta from the microgrid after the storage has been
                (de)charged. If negative, this power must be drawn from the public grid.
                If positive, the power can be fed to the public grid or must be curtailed.
            actor_infos: Contains the last "info" dictionaries by all actors in the
                microgrid. The info dictionary is defined by the actor and can contain
                any information about the actor's state.
        """

    def finalize(self) -> None:
        """This method can be overridden clean-up after the simulation finished."""


class Monitor(Controller):
    def __init__(
        self,
        step_size: Optional[int] = None,
        monitor_storage=True,
        monitor_grid_signals=True,
    ):
        super().__init__(step_size=step_size)
        self.monitor_storage = monitor_storage
        self.monitor_grid_signals = monitor_grid_signals
        self.monitor_log: dict[datetime, dict] = defaultdict(dict)
        self.custom_monitor_fns: list[Callable] = []
        self.clock: Optional[Clock] = None

    def start(self, microgrid: Microgrid, clock: Clock, grid_signals: dict) -> None:
        self.clock = clock
        if self.monitor_storage:
            if microgrid.storage is None:
                raise ValueError("Cannot monitor storage if no storage is present.")
            storage_state = microgrid.storage.state()
            self.add_monitor_fn(lambda _: {"storage": storage_state})

        if self.monitor_grid_signals:
            for signal_name, signal_api in grid_signals.items():

                def fn(time):
                    return {signal_name: signal_api.at(clock.to_datetime(time))}

                self.add_monitor_fn(fn)

    def add_monitor_fn(self, fn: Callable[[float], dict[str, Any]]):
        self.custom_monitor_fns.append(fn)

    def step(self, time: int, p_delta: float, actor_infos: dict) -> None:
        self.monitor(time, p_delta, actor_infos)

    def monitor(self, time: int, p_delta: float, actor_infos: dict) -> None:
        log_entry = dict(
            p_delta=p_delta,
            actor_infos=actor_infos,
        )
        for monitor_fn in self.custom_monitor_fns:
            log_entry.update(monitor_fn(time))
        assert self.clock is not None  # clock is initialized at this point
        self.monitor_log[self.clock.to_datetime(time)] = log_entry

    def to_csv(self, out_path: str):
        df = pd.DataFrame({k: flatten_dict(v) for k, v in self.monitor_log.items()}).T
        df.to_csv(out_path)


def flatten_dict(d: MutableMapping, parent_key: str = "") -> MutableMapping:
    items: list[tuple[str, Any]] = []
    for k, v in d.items():
        new_key = parent_key + "." + k if parent_key else k
        if isinstance(v, MutableMapping):
            items.extend(flatten_dict(v, str(new_key)).items())
        else:
            items.append((new_key, v))
    return dict(items)


class ControllerSim(mosaik_api.Simulator):
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
        self.controller: Optional[Controller] = None

    def init(self, sid, time_resolution=1.0, **sim_params):
        self.step_size = sim_params["step_size"]
        return self.meta

    def create(self, num, model, **model_params):
        assert num == 1, "Only one instance per simulation is supported"
        self.controller = model_params["controller"]
        return [{"eid": self.eid, "type": model}]

    def step(self, time, inputs, max_advance):
        assert self.controller is not None
        try:
            self.controller.step(time, *_parse_controller_inputs(inputs[self.eid]))
        except KeyError:
            self.controller.step(time, p_delta=0, actor_infos={})
        return time + self.step_size

    def get_data(self, outputs):
        return {}  # TODO so far unused

    def finalize(self) -> None:
        """Stops the api server and the collector thread when the simulation finishes."""
        assert self.controller is not None
        self.controller.finalize()


def _parse_controller_inputs(inputs: dict[str, dict[str, Any]]) -> tuple[float, dict]:
    try:
        p_delta = _get_val(inputs, "p_delta")
    except KeyError:
        p_delta = None  # in case there has not yet been any power reported by actors
    actor_keys = [k for k in inputs.keys() if k.startswith("actor")]
    actors: defaultdict[str, Any] = defaultdict(dict)
    for k in actor_keys:
        _, actor_name = k.split(".")
        actors[actor_name] = _get_val(inputs, k)
    assert p_delta is not None
    return p_delta, dict(actors)


def _get_val(inputs: dict, key: str) -> Any:
    return list(inputs[key].values())[0]
