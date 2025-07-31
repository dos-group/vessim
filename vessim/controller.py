from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from csv import DictWriter
from itertools import count
from collections.abc import Iterator
from typing import Any, Optional, TYPE_CHECKING
import multiprocessing
import time

import mosaik_api_v3  # type: ignore

if TYPE_CHECKING:
    from vessim.microgrid import Microgrid, MicrogridState


class Controller(ABC):
    _counters: dict[type[Controller], Iterator[int]] = {}

    def __init_subclass__(cls, **kwargs) -> None:
        """Initializes the subclass and sets up a counter for naming."""
        super().__init_subclass__(**kwargs)
        cls._counters[cls] = count()

    def __init__(self, microgrids: list[Microgrid], step_size: Optional[int] = None) -> None:
        cls = self.__class__
        self.name: str = f"{cls.__name__}-{next(cls._counters[cls])}"
        self.step_size = step_size
        self.set_parameters: dict[str, Any] = {}
        self.microgrids: dict[str, Microgrid] = {mg.name: mg for mg in microgrids}

    @abstractmethod
    def step(self, time: datetime, microgrid_states: dict[str, MicrogridState]) -> None:
        """Performs a simulation step across all managed microgrids.

        Args:
            time: Current datetime.
            microgrid_states: Maps microgrid names to their current state.
        """

    def finalize(self) -> None:
        """Executed after simulation has ended. Can be overridden for clean-up."""
        pass


class Monitor(Controller):
    def __init__(
        self,
        microgrids: list[Microgrid],
        step_size: Optional[int] = None,
        outfile: Optional[str | Path] = None,
    ):
        super().__init__(microgrids, step_size=step_size)
        self.outfile: Optional[Path] = Path(outfile) if outfile else None
        self._fieldnames: dict[str, Optional[list]] = {}  # Per microgrid fieldnames
        self.log: dict[datetime, dict[str, MicrogridState]] = defaultdict(dict)

    def step(self, t: datetime, microgrid_states: dict[str, MicrogridState]) -> None:
        self.log[t] = microgrid_states
        if self.outfile is not None:
            self._write_microgrid_csv(t, microgrid_states, outfile=self.outfile)

    def to_csv(self, outfile: str | Path):
        """Export current log to a CSV file."""
        for t, migrogrid_states in self.log.items():
            self._write_microgrid_csv(t, migrogrid_states, outfile=Path(outfile))

    def _write_microgrid_csv(
        self,
        time: datetime,
        microgrid_states: dict[str, MicrogridState],
        outfile: Path,
    ) -> None:
        """Append microgrid states to CSV file."""
        outfile.parent.mkdir(exist_ok=True, parents=True)
        for mg_name, migrogrid_state in microgrid_states.items():
            log_entry = {
                "microgrid": mg_name,
                "time": time,
                **_flatten_dict(dict(migrogrid_state))
            }

            if mg_name not in self._fieldnames:  # First time: create file with header
                self._fieldnames[mg_name] = list(log_entry.keys())
                mode, write_header = "w", True
            else:
                mode, write_header = "a", False

            with outfile.open(mode, newline="") as csvfile:
                fieldnames = self._fieldnames[mg_name]
                assert fieldnames is not None
                writer = DictWriter(csvfile, fieldnames=fieldnames)
                if write_header:
                    writer.writeheader()
                writer.writerow(log_entry)


class Api(Controller):
    """REST API interface for microgrid data and control."""

    def __init__(
        self,
        microgrids: list[Microgrid],
        step_size: Optional[int] = None,
        export_prometheus: bool = False,
        broker_port: int = 8700,
    ):
        try:
            import requests

            self.requests = requests
        except ImportError:
            raise ImportError(
                "RestInterface requires 'requests' package. " "Install with: pip install requests"
            )

        super().__init__(microgrids, step_size=step_size)
        self.broker_port = broker_port
        self.broker_url = f"http://localhost:{broker_port}"
        self.broker_process: Optional[multiprocessing.Process] = None
        self.export_prometheus = export_prometheus

        self._start_broker()
        self._register_microgrids()

    def _start_broker(self):
        from vessim._broker import run_broker

        self.broker_process = multiprocessing.Process(
            target=run_broker,
            args=(self.broker_port, self.export_prometheus),
            daemon=True
        )
        self.broker_process.start()
        time.sleep(2)
        prometheus_str = " (incl. Prometheus exporter)" if self.export_prometheus else ""
        print(f"🌐 API{prometheus_str} available at: {self.broker_url}")

    def _register_microgrids(self):
        for mg_name, mg in self.microgrids.items():
            config = {
                "name": mg_name,
                "actors": [actor.name for actor in mg.actors],
                "storage": mg.storage.__class__.__name__ if mg.storage else None,
            }
            self.requests.post(f"{self.broker_url}/internal/microgrids/{mg_name}", json=config)

    def step(self, time: datetime, microgrid_states: dict[str, MicrogridState]) -> None:
        """Push data to broker and process commands."""
        self._process_commands()

        for mg_name, mg_state in microgrid_states.items():
            data = {
                'microgrid': mg_name,
                'time': time.isoformat(),
                **mg_state
            }
            self.requests.post(f"{self.broker_url}/internal/data/{mg_name}", json=data)

    def _process_commands(self):
        response = self.requests.get(f"{self.broker_url}/internal/commands")
        commands = response.json().get("commands", [])

        for command in commands:
            if command.get("type") == "set_parameter":
                microgrid = command.get("microgrid")
                parameter = command.get("parameter")
                value = command.get("value")
                if microgrid and parameter and value is not None:
                    key = f"{microgrid}:{parameter}"
                    self.set_parameters[key] = value

    def finalize(self) -> None:
        """Clean up resources when simulation ends."""
        if self.broker_process and self.broker_process.is_alive():
            self.broker_process.terminate()
            self.broker_process.join(timeout=2)

        print("🛑 API broker terminated")


class _ControllerSim(mosaik_api_v3.Simulator):
    META = {
        "type": "time-based",
        "models": {
            "Controller": {
                "public": True,
                "params": ["controller", "microgrid_names"],
                "attrs": [
                    "p_delta",
                    "p_grid",
                    "actor_states",
                    "policy_state",
                    "storage_state",
                    "grid_signals",
                    "set_parameters",
                ],
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

        data = inputs[self.eid]
        microgrids = [key.split(".grid.Grid")[0] for key in data["p_delta"].keys()]
        microgrid_states: dict[str, MicrogridState] = {name: {
            "p_delta": data["p_delta"][f"{name}.grid.Grid"],
            "p_grid": data["p_grid"][f"{name}.storage.Storage"],
            "actor_states": {k.split(".")[-1]: data["actor_states"][k] for k  in data["actor_states"].keys() if k.startswith(f"{name}.actor.")},  # noqa: E501
            "policy_state": next(v for k, v in data["policy_state"].items() if k.startswith(f"{name}.storage.Storage")),  # noqa: E501
            "storage_state": next((v for k, v in data["storage_state"].items() if k.startswith(f"{name}.storage.Storage")), None),  # noqa: E501
            "grid_signals": next((v for k, v in data["grid_signals"].items() if k.startswith(f"{name}.grid.Grid")), None),  # noqa: E501
        } for name in microgrids}

        now = self.clock.to_datetime(time)
        self.controller.step(now, microgrid_states)

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

def _flatten_dict(d: dict, parent_key: str = "") -> dict:
    items: list[tuple[str, Any]] = []
    for k, v in d.items():
        new_key = parent_key + "." + k if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, str(new_key)).items())
        else:
            items.append((new_key, v))
    return dict(items)
