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

    def __init__(self, microgrids: list["Microgrid"], step_size: Optional[int] = None) -> None:
        cls = self.__class__
        self.name: str = f"{cls.__name__}-{next(cls._counters[cls])}"
        self.step_size = step_size
        self.set_parameters: dict[str, Any] = {}
        self.microgrids: dict[str, "Microgrid"] = {mg.name: mg for mg in microgrids}

    @abstractmethod
    def step(self, time: datetime, microgrid_states: dict[str, dict[str, Any]]) -> None:
        """Performs a simulation step across all managed microgrids.

        Args:
            time: Current datetime.
            microgrid_states: Dictionary mapping microgrid names to their state dictionaries.
                Each state dictionary contains:
                - "p_delta": Power delta in W based on consumption and production of all actors
                - "p_grid": Power in W drawn from/fed to the utility grid in the previous step
                - "state": Dictionary containing actor states, policy state, and storage state
                    The keys are actor names, "policy", and "storage" respectively.
        """

    def finalize(self) -> None:
        """Function to be executed after simulation has ended. Can be overridden for clean-up."""
        pass


class Monitor(Controller):
    def __init__(
        self,
        microgrids: list["Microgrid"],
        step_size: Optional[int] = None,
        outdir: Optional[str | Path] = None,
        grid_signals: Optional[dict[str, Signal]] = None,
    ):
        super().__init__(microgrids, step_size=step_size)
        self.outdir: Optional[Path] = None

        if outdir:
            self.outdir = Path(outdir).expanduser()
            self.outdir.mkdir(parents=True, exist_ok=True)

        self._fieldnames: dict[str, Optional[list]] = {}  # Per microgrid fieldnames

        # Hierarchical log: datetime -> microgrid_name -> entry
        self.log: dict[datetime, dict[str, dict]] = defaultdict(dict)
        self.custom_monitor_fns: list[Callable] = []

        if grid_signals is not None:
            for signal_name, signal_api in grid_signals.items():

                def fn(time):
                    return {signal_name: signal_api.now(time)}

                self.add_monitor_fn(fn)

    def add_monitor_fn(self, fn: Callable[[float], dict[str, Any]]):
        self.custom_monitor_fns.append(fn)

    def step(self, time: datetime, microgrid_states: dict[str, dict[str, Any]]) -> None:
        # Build hierarchical log structure: datetime -> microgrid_name -> entry
        for mg_name, mg_state in microgrid_states.items():
            log_entry = dict(
                p_delta=mg_state["p_delta"],
                p_grid=mg_state["p_grid"],
            )
            log_entry.update(mg_state["state"])
            for monitor_fn in self.custom_monitor_fns:
                log_entry.update(monitor_fn(time))

            # Store in hierarchical structure
            self.log[time][mg_name] = log_entry

            # Write separate CSV per microgrid if output directory specified
            if self.outdir:
                self._write_microgrid_csv(time, mg_name, log_entry)

    def _write_microgrid_csv(self, time: datetime, mg_name: str, log_entry: dict) -> None:
        """Write log entry to a microgrid-specific CSV file."""
        csv_path = self.outdir / f"{mg_name}.csv"
        log_dict = _flatten_dict(log_entry)
        log_dict["time"] = time

        if mg_name not in self._fieldnames:
            # First time writing this microgrid - create file with header
            self._fieldnames[mg_name] = ["time"] + list(log_dict.keys())
            mode, write_header = "w", True
        else:
            mode, write_header = "a", False

        with csv_path.open(mode, newline='') as csvfile:
            writer = DictWriter(csvfile, fieldnames=self._fieldnames[mg_name])
            if write_header:
                writer.writeheader()
            writer.writerow(log_dict)

    def _get_microgrid_records(self, microgrid_name: str) -> list[dict]:
        """Extract records for a specific microgrid."""
        records = []
        for time, microgrids in self.log.items():
            if microgrid_name in microgrids:
                record = {"time": time}
                record.update(_flatten_dict(microgrids[microgrid_name]))
                records.append(record)
        return records

    def to_csv(self, out_path: str | Path, microgrid_name: Optional[str] = None):
        """Export logs to CSV.
        
        Args:
            out_path: Output file path
            microgrid_name: If specified, export only this microgrid's data. 
                          If None, export all microgrids with microgrid column.
        """
        if microgrid_name:
            records = self._get_microgrid_records(microgrid_name)
        else:
            # Export all microgrids with microgrid column
            records = []
            for time, microgrids in self.log.items():
                for mg_name, mg_data in microgrids.items():
                    record = {"time": time, "microgrid": mg_name}
                    record.update(_flatten_dict(mg_data))
                    records.append(record)

        pd.DataFrame(records).to_csv(out_path, index=False)

    def to_csv_per_microgrid(self, output_dir: str | Path):
        """Export separate CSV file for each microgrid."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get all unique microgrid names
        all_microgrids = {mg_name for microgrids in self.log.values() for mg_name in microgrids.keys()}

        # Export each microgrid separately
        for mg_name in all_microgrids:
            self.to_csv(output_dir / f"{mg_name}.csv", microgrid_name=mg_name)


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
                "params": ["controller", "microgrid_names"],
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
        self.microgrid_names = []
        self.microgrid_states: dict[str, dict[str, Any]] = {}
        self.last_step_time = None

    def init(self, sid, time_resolution=1.0, **sim_params):
        self.step_size = sim_params["step_size"]
        self.clock = sim_params["clock"]
        return self.meta

    def create(self, num, model, **model_params):
        assert num == 1, "Only one instance per simulation is supported"
        self.controller = model_params["controller"]
        self.microgrid_names = model_params["microgrid_names"]
        return [{"eid": self.eid, "type": model}]

    def step(self, time, inputs, max_advance):
        assert self.controller is not None
        assert self.clock is not None
        assert self.step_size is not None
        now = self.clock.to_datetime(time)

        microgrid_states = defaultdict(lambda: {"p_delta": 0.0, "p_grid": 0.0, "state": {}})

        # Add actor values
        for k, v in inputs[self.eid].items():
            if k in ['p_delta', 'p_grid', 'state']:
                continue
            microgrid = k.split('.')[0]
            microgrid_states[microgrid]["state"][k] = list(v.values())[0]  # e.g. {'p': -400}

        # Add p_delta and p_grid
        for metric in ['p_delta', 'p_grid']:
            for full_key, value in inputs[self.eid][metric].items():
                microgrid = full_key.split('.')[0]
                microgrid_states[microgrid][metric] = value

        # Add storage state
        for full_key, value in inputs[self.eid]['state'].items():
            microgrid = full_key.split('.')[0]
            microgrid_states[microgrid]["state"][full_key] = value

        # Call controller with all microgrid states
        self.controller.step(now, dict(microgrid_states))

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
        p_grid = _get_val(inputs, "p_grid")
        actor_keys = [k for k in inputs.keys() if k.startswith("actor")]
        actors: defaultdict[str, Any] = defaultdict(dict)
        for k in actor_keys:
            _, actor_name = k.split(".")
            actors[actor_name] = _get_val(inputs, k)
        state = dict(actors)
        state.update(_get_val(inputs, "state"))
        return p_delta, p_grid, state


def _get_val(inputs: dict, key: str) -> Any:
    return list(inputs[key].values())[0]
