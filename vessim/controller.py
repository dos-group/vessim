from __future__ import annotations

import multiprocessing
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from csv import DictWriter
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

import mosaik_api_v3  # type: ignore
from loguru import logger

from vessim._util import flatten_dict

if TYPE_CHECKING:
    from vessim.environment import Environment
    from vessim.microgrid import Microgrid, MicrogridState


def _build_experiment_config(environment: Environment) -> dict:
    """Build the static experiment configuration dict shared by loggers."""
    return {
        "environment": {
            "name": environment.name,
            "sim_start": str(environment.clock.sim_start),
            "step_size": environment.step_size,
        },
        "microgrids": {
            mg.name: {
                "actors": [actor.config() for actor in mg.actors],
                "dispatchables": [
                    {"name": d.name, "type": d.__class__.__name__, **d.config()}
                    for d in mg.dispatchables
                ],
                "policy": {
                    "type": mg.policy.__class__.__name__,
                    **mg.policy.state(),
                },
                "grid_signals": (
                    {name: str(signal) for name, signal in mg.grid_signals.items()}
                    if mg.grid_signals else None
                ),
                "coords": mg.coords,
            }
            for mg in environment.microgrids
        },
    }


class Controller(ABC):
    """Abstract base class for all controllers in the simulation.

    Controllers are used to monitor the simulation state and to control the
    behavior of the microgrids. They are executed at every simulation step.
    """

    def start(self, environment: Environment) -> None:
        """Executed before the simulation starts.

        Can be overridden to inspect the simulation topology or perform initialization
        that requires access to the `Environment`.
        """

    @abstractmethod
    def step(self, now: datetime, microgrid_states: dict[str, MicrogridState]) -> None:
        """Performs a simulation step.

        Args:
            now: Current datetime in the simulation.
            microgrid_states: Maps microgrid names to their current state.
        """

    def finalize(self) -> None:
        """Executed after simulation has ended. Can be overridden for clean-up."""


class MemoryLogger(Controller):
    """Controller that logs the state of the simulation in memory.

    The logged state can be retrieved as a dictionary or a pandas DataFrame.
    After the simulation, ``config`` contains the static experiment metadata
    (same information that ``CsvLogger`` writes to ``metadata.yaml``).
    """

    def __init__(self):
        self.log: dict[datetime, dict[str, MicrogridState]] = defaultdict(dict)
        self.config: dict = {}

    def start(self, environment: Environment) -> None:
        self.config = _build_experiment_config(environment)

    def step(self, now: datetime, microgrid_states: dict[str, MicrogridState]) -> None:
        self.log[now] = microgrid_states

    def to_dict(self) -> dict[datetime, dict[str, MicrogridState]]:
        """Returns the logged data as a dictionary."""
        return dict(self.log)

    def to_df(self):
        """Returns the logged data as a pandas DataFrame.

        The DataFrame has a MultiIndex (time, microgrid) and columns for each
        state variable. Requires 'pandas' to be installed.
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError(
                "MemoryLogger.to_df() requires 'pandas'. "
                "Install with: pip install pandas"
            )

        data = []
        for t, microgrid_states in self.log.items():
            for mg_name, state in microgrid_states.items():
                row = flatten_dict(state)
                row["time"] = t
                row["microgrid"] = mg_name
                data.append(row)

        df = pd.DataFrame(data)
        if not df.empty:
            df = df.set_index(["time", "microgrid"])
        return df


class CsvLogger(Controller):
    """Controller that logs simulation results to a directory.

    Writes two files:
    - ``metadata.yaml``: static experiment configuration (run metadata, microgrid
      topology, actor and dispatchable parameters) written once before the simulation
      starts.
    - ``timeseries.csv``: dynamic state logged at every simulation step.

    Args:
        outdir: Path to the output directory (created if it doesn't exist).
    """

    def __init__(self, outdir: str | Path):
        self.outdir = Path(outdir)
        self.outdir.mkdir(exist_ok=True, parents=True)
        self.csv_path = self.outdir / "timeseries.csv"
        self.fieldnames: dict[str, list] = {}
        self._last_sim_time: Optional[datetime] = None

    def start(self, environment: Environment) -> None:
        try:
            import yaml
        except ImportError:
            raise ImportError(
                "CsvLogger requires 'pyyaml'. Install with: pip install pyyaml"
            )

        self._yaml = yaml

        git_hash: Optional[str] = None
        try:
            import subprocess
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, check=True,
            )
            git_hash = result.stdout.strip()
        except Exception:
            pass

        config = _build_experiment_config(environment)
        config["execution"] = {
            "status": "running",
            "git_hash": git_hash,
            "start": datetime.now().isoformat(),
            "end": None,
            "duration": None,
        }

        self._exec_start = datetime.now()
        with (self.outdir / "metadata.yaml").open("w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    def step(self, now: datetime, microgrid_states: dict[str, MicrogridState]) -> None:
        self._last_sim_time = now
        for mg_name, mg_state in microgrid_states.items():
            log_entry = {
                "microgrid": mg_name,
                "time": now,
                **flatten_dict(dict(mg_state)),
            }

            if mg_name not in self.fieldnames:
                self.fieldnames[mg_name] = list(log_entry.keys())
                mode, write_header = "w", True
            else:
                mode, write_header = "a", False

            with self.csv_path.open(mode, newline="") as csvfile:
                writer = DictWriter(csvfile, fieldnames=self.fieldnames[mg_name])
                if write_header:
                    writer.writeheader()
                writer.writerow(log_entry)

    def finalize(self) -> None:
        experiment_path = self.outdir / "metadata.yaml"
        if experiment_path.exists() and hasattr(self, "_yaml"):
            end = datetime.now()
            with experiment_path.open() as f:
                config = self._yaml.safe_load(f)
            config["execution"]["status"] = "completed"
            config["execution"]["end"] = end.isoformat()
            config["execution"]["duration"] = round((end - self._exec_start).total_seconds(), 3)
            if self._last_sim_time is not None:
                config["environment"]["sim_end"] = str(self._last_sim_time)
            with experiment_path.open("w") as f:
                self._yaml.dump(config, f, default_flow_style=False, sort_keys=False)


class Api(Controller):
    """REST API interface for microgrid data and control.

    The API controller starts a background process with a FastAPI-based broker
    that exposes endpoints to query the current state of the microgrids and to
    send control commands to them.

    Args:
        export_prometheus: Whether to export metrics to Prometheus. Defaults to False.
        broker_port: The port on which the API broker should run. Defaults to 8700.
    """

    def __init__(
        self,
        export_prometheus: bool = False,
        broker_port: int = 8700,
    ):
        try:
            import requests

            self.requests = requests
        except ImportError:
            raise ImportError(
                "Api requires 'requests' package. Install with: pip install vessim[sil]"
            )

        self.broker_port = broker_port
        self.broker_url = f"http://localhost:{broker_port}"
        self.broker_process: Optional[multiprocessing.Process] = None
        self.export_prometheus = export_prometheus
        self.microgrids: dict[str, Microgrid] = {}

    def start(self, environment: Environment) -> None:
        microgrids = {mg.name: mg for mg in environment.microgrids}
        self.microgrids = microgrids
        self._start_broker()
        for mg_name, mg in microgrids.items():
            config = {
                "name": mg_name,
                "actors": [actor.config() for actor in mg.actors],
                "dispatch": [
                    {
                        "name": d.name,
                        "type": d.__class__.__name__,
                        **d.config(),
                    }
                    for d in mg.dispatchables
                ],
                "policy": {
                    "type": mg.policy.__class__.__name__,
                    **mg.policy.state(),
                },
                "coords": mg.coords,
            }
            self.requests.post(f"{self.broker_url}/internal/microgrids/{mg_name}", json=config)
        print(f"Registered {len(microgrids)} microgrids with API broker.")

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

    def step(self, now: datetime, microgrid_states: dict[str, MicrogridState]) -> None:
        """Process commands and push microgrid states to broker."""
        response = self.requests.get(f"{self.broker_url}/internal/commands")
        commands = response.json().get("commands", [])
        for cmd in commands:
            if cmd.get("type") == "set_parameter":
                microgrid_name = cmd.get("microgrid")
                if microgrid_name not in self.microgrids:
                    continue

                mg = self.microgrids[microgrid_name]
                target = cmd.get("target")
                prop = cmd.get("property")
                val = cmd.get("value")

                if target == "dispatchable":
                    target_name = cmd.get("target_name")
                    d = next((d for d in mg.dispatchables if d.name == target_name), None)
                    if d:
                        setattr(d, prop, val)
                elif target == "policy":
                    setattr(mg.policy, prop, val)
                elif target == "actor":
                    actor_name = cmd.get("target_name")
                    actor = next((a for a in mg.actors if a.name == actor_name), None)
                    if actor and hasattr(actor.signal, "set_value"):
                        actor.signal.set_value(val)

        for mg_name, mg_state in microgrid_states.items():
            self.requests.post(
                f"{self.broker_url}/internal/data/{mg_name}",
                json={"microgrid": mg_name, "time": now.isoformat(), **mg_state},
            )

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
                "params": ["controllers"],
                "attrs": [
                    "p_delta",
                    "p_grid",
                    "actor_states",
                    "policy_state",
                    "dispatch_states",
                    "grid_signals",
                ],
            },
        },
    }

    def __init__(self):
        super().__init__(self.META)
        self.eid = "Controller"
        self.step_size = None
        self.clock = None
        self.controllers: list[Controller] = []
        self.microgrid_states: dict[str, dict[str, Any]] = {}

    def init(self, sid, time_resolution=1.0, **sim_params):
        self.step_size = sim_params["step_size"]
        self.clock = sim_params["clock"]
        return self.meta

    def create(self, num, model, **model_params):
        assert num == 1, "Only one instance per simulation is supported"
        self.controllers = model_params["controllers"]
        return [{"eid": self.eid, "type": model}]

    def step(self, time, inputs, max_advance):
        assert self.clock is not None
        assert self.step_size is not None

        data = inputs[self.eid]
        mg_suffix = ".microgrid.Microgrid"
        microgrids = [key.removesuffix(mg_suffix) for key in data["p_delta"].keys()]
        microgrid_states: dict[str, MicrogridState] = {name: {
            "p_delta": data["p_delta"][f"{name}{mg_suffix}"],
            "p_grid": data["p_grid"][f"{name}{mg_suffix}"],
            "actor_states": {k.split(".")[-1]: data["actor_states"][k] for k in data["actor_states"].keys() if k.startswith(f"{name}.actor.")},  # noqa: E501
            "policy_state": data["policy_state"].get(f"{name}{mg_suffix}", {}),
            "dispatch_states": data.get("dispatch_states", {}).get(f"{name}{mg_suffix}"),
            "grid_signals": data["grid_signals"].get(f"{name}{mg_suffix}"),
        } for name in microgrids}

        now = self.clock.to_datetime(time)
        for controller in self.controllers:
            controller.step(now, microgrid_states)

        return time + self.step_size

    def finalize(self) -> None:
        """Stops the api server and the collector thread when the simulation finishes."""
        for controller in self.controllers:
            controller.finalize()
