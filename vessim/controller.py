from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from csv import DictWriter
from itertools import count
from collections.abc import Iterator
from typing import Any, MutableMapping, Optional, Callable, TYPE_CHECKING

import mosaik_api_v3  # type: ignore
import pandas as pd

from vessim.signal import Signal

if TYPE_CHECKING:
    from vessim.cosim import Microgrid


class Controller(ABC):
    _counters: dict[type[Controller], Iterator[int]] = {}

    def __init_subclass__(cls, **kwargs) -> None:
        """Initializes the subclass and sets up a counter for naming."""
        super().__init_subclass__(**kwargs)
        cls._counters[cls] = count()

    def __init__(self, step_size: Optional[int] = None) -> None:
        cls = self.__class__
        self.name: str = f"{cls.__name__}-{next(cls._counters[cls])}"
        self.step_size = step_size
        self.set_parameters: dict[str, Any] = {}

    def start(self, microgrid: Microgrid) -> None:
        """Function to be executed before simulation is started. Can be overridden."""
        pass

    @abstractmethod
    def step(self, time: datetime, p_delta: float, e_delta: float, state: dict) -> None:
        """Performs a simulation step.

        Args:
            time: Current datetime.
            p_delta: Power delta in W based on the consumption and production of all actors.
            e_delta: Total energy in Ws that has been drawn from/ fed to the utility grid
                in the previous time step.
            state: Contains the last state dictionaries by all actors, the policy, and the storage
                in the microgrid. The state dictionary is defined by the microgrid components and
                can contain any information about their custom defined state.
                The keys are the actor names, `policy`, and `storage` respectively.
        """

    def finalize(self) -> None:
        """Function to be executed after simulation has ended. Can be overridden for clean-up."""
        pass


class Monitor(Controller):
    def __init__(
        self,
        step_size: Optional[int] = None,
        outfile: Optional[str | Path] = None,
        grid_signals: Optional[dict[str, Signal]] = None,
    ):
        super().__init__(step_size=step_size)
        self.outpath: Optional[Path] = None
        if outfile:
            self.outpath = Path(outfile).expanduser()
        self._fieldnames: Optional[list] = None

        self.monitor_log: dict[datetime, dict] = defaultdict(dict)
        self.custom_monitor_fns: list[Callable] = []

        if grid_signals is not None:
            for signal_name, signal_api in grid_signals.items():

                def fn(time):
                    return {signal_name: signal_api.now(time)}

                self.add_monitor_fn(fn)

    def add_monitor_fn(self, fn: Callable[[float], dict[str, Any]]):
        self.custom_monitor_fns.append(fn)

    def step(self, time: datetime, p_delta: float, e_delta: float, state: dict) -> None:
        log_entry = dict(
            p_delta=p_delta,
            e_delta=e_delta,
        )
        log_entry.update(state)
        for monitor_fn in self.custom_monitor_fns:
            log_entry.update(monitor_fn(time))
        self.monitor_log[time] = log_entry

        if self.outpath:
            if not self._fieldnames:
                log_dict = _flatten_dict(log_entry)
                self._fieldnames = list(log_dict.keys())
                self._fieldnames.insert(0, "time")
                log_dict["time"] = time
                with self.outpath.open("w") as csvfile:
                    writer = DictWriter(csvfile, fieldnames=self._fieldnames)
                    writer.writeheader()
                    writer.writerow(log_dict)
            else:
                with self.outpath.open('a', newline='') as csvfile:
                    writer = DictWriter(csvfile, fieldnames=self._fieldnames)
                    log_dict = _flatten_dict(log_entry)
                    log_dict["time"] = time
                    writer.writerow(log_dict)

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
                "attrs": ["set_parameters"],
            },
        },
    }

    def __init__(self):
        super().__init__(self.META)
        self.eid = "Controller"
        self.step_size = None
        self.clock = None
        self.controller = None
        self.e = 0.0

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
        assert self.clock is not None
        assert self.step_size is not None
        now = self.clock.to_datetime(time)
        self.controller.step(now, *self._parse_controller_inputs(inputs[self.eid]))
        self.set_parameters = self.controller.set_parameters.copy()
        self.controller.set_parameters = {}
        return time + self.step_size

    def get_data(self, outputs):
        return {self.eid: {"set_parameters": self.set_parameters}}

    def finalize(self) -> None:
        """Stops the api server and the collector thread when the simulation finishes."""
        assert self.controller is not None
        self.controller.finalize()

    def _parse_controller_inputs(
        self, inputs: dict[str, dict[str, Any]]
    ) -> tuple[float, float, dict]:
        p_delta = _get_val(inputs, "p_delta")
        last_e = self.e
        self.e = _get_val(inputs, "e")
        actor_keys = [k for k in inputs.keys() if k.startswith("actor")]
        actors: defaultdict[str, Any] = defaultdict(dict)
        for k in actor_keys:
            _, actor_name = k.split(".")
            actors[actor_name] = _get_val(inputs, k)
        state = dict(actors)
        state.update(_get_val(inputs, "state"))
        return p_delta, self.e - last_e, state


def _get_val(inputs: dict, key: str) -> Any:
    return list(inputs[key].values())[0]
