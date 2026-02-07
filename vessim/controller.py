from __future__ import annotations

import multiprocessing
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from csv import DictWriter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

import mosaik_api_v3  # type: ignore
import requests

from vessim._util import flatten_dict
from vessim.influx_writer import InfluxConfig, InfluxWriter

if TYPE_CHECKING:
    from vessim.microgrid import Microgrid, MicrogridState
    from vessim.actor import Actor


class Controller(ABC):
    """Abstract base class for all controllers in the simulation.

    Controllers are used to monitor the simulation state and to control the
    behavior of the microgrids. They are executed at every simulation step.
    """

    def start(self, microgrids: dict[str, Microgrid]) -> None:
        """Executed before the simulation starts.

        Can be overridden to inspect the simulation topology or perform initialization
        that requires access to the `Microgrid` objects.
        """
        pass

    @abstractmethod
    def step(self, now: datetime, microgrid_states: dict[str, MicrogridState]) -> None:
        """Performs a simulation step.

        Args:
            now: Current datetime in the simulation.
            microgrid_states: Maps microgrid names to their current state.
        """
        pass

    def finalize(self) -> None:
        """Executed after simulation has ended. Can be overridden for clean-up."""
        pass


class MemoryLogger(Controller):
    """Controller that logs the state of the simulation in memory.

    The logged state can be retrieved as a dictionary or a pandas DataFrame.
    """

    def __init__(self):
        self.log: dict[datetime, dict[str, MicrogridState]] = defaultdict(dict)

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
    """Controller that writes the state of the simulation to a CSV file.

    The state is written to the file at each simulation step (streaming), so
    it doesn't consume memory for the history.

    Args:
        outfile: Path to the CSV file.
    """

    def __init__(self, outfile: str | Path):
        self.filepath = Path(outfile)
        self.fieldnames: dict[str, list] = {}
        self.filepath.parent.mkdir(exist_ok=True, parents=True)

    def step(self, now: datetime, microgrid_states: dict[str, MicrogridState]) -> None:
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

            with self.filepath.open(mode, newline="") as csvfile:
                writer = DictWriter(csvfile, fieldnames=self.fieldnames[mg_name])
                if write_header:
                    writer.writeheader()
                writer.writerow(log_entry)


class Monitor(Controller):
    """Controller that logs simulation data to InfluxDB and optionally to CSV.
    
    The Monitor streams simulation data in real-time directly to InfluxDB, 
    which can then be visualized in Grafana. Actors are grouped by tags 
    (e.g., `solar`, `compute`) for organized monitoring.

    Args:
        outfile: Optional path to a CSV file for logging.
        influx_config: InfluxDB configuration for real-time streaming.
        sim_id: Optional simulation ID for filtering in InfluxDB.
        write_csv: Whether to write to CSV file. Defaults to True.
    """

    def __init__(
        self,
        outfile: Optional[str | Path] = None,
        influx_url: Optional[str] = None,
        influx_bucket: Optional[str] = None,
        influx_token: Optional[str] = None,
        influx_org: Optional[str] = None,
        influx_config: Optional[InfluxConfig] = None,
        sim_id: Optional[str] = None,
        write_csv: bool = True,
    ):
        self.outfile = Path(outfile) if outfile else None
        self.write_csv = write_csv
        self.sim_id = sim_id
        self.log: dict[datetime, dict[str, MicrogridState]] = defaultdict(dict)

        self.influx_url = influx_url
        self.influx_bucket = influx_bucket
        self.influx_token = influx_token
        self.influx_org = influx_org

        self._influx_writer: Optional[InfluxWriter] = None
        if influx_config is not None:
            self._influx_writer = InfluxWriter(influx_config)
        elif influx_url and influx_bucket and influx_token and influx_org:
            self._influx_writer = InfluxWriter(InfluxConfig(
                url=influx_url,
                token=influx_token,
                org=influx_org,
                bucket=influx_bucket,
            ))

        self.microgrids: dict[str, Microgrid] = {}
        self._actor_lookup: dict[str, dict[str, Actor]] = {}
        self._csv_logger: Optional[CsvLogger] = None

    def start(self, microgrids: dict[str, Microgrid]) -> None:
        self.microgrids = microgrids
        for mg_name, mg in microgrids.items():
            self._actor_lookup[mg_name] = {actor.name: actor for actor in mg.actors}
        
        if self.write_csv and self.outfile:
            self._csv_logger = CsvLogger(self.outfile)

    def step(self, now: datetime, microgrid_states: dict[str, MicrogridState]) -> None:
        self.log[now] = microgrid_states

        if self._csv_logger:
            self._csv_logger.step(now, microgrid_states)

        if self._influx_writer is not None and self._influx_writer.is_available:
            self._write_to_influx(now, microgrid_states)

    def _write_to_influx(
        self,
        t: datetime,
        microgrid_states: dict[str, MicrogridState],
    ) -> None:
        """Write data to InfluxDB in real-time."""
        if self._influx_writer is None:
            return

        for mg_name, state in microgrid_states.items():
            actor_lookup = self._actor_lookup.get(mg_name, {})
            actor_states = state.get("actor_states", {}) or {}
            actor_values: dict = {}
            tag_sums: dict[str, float] = defaultdict(float)

            for actor_name, a_state in actor_states.items():
                power = a_state.get("power")
                if power is None or not isinstance(power, (int, float)):
                    continue
                actor = actor_lookup.get(actor_name)
                if actor is not None:
                    actor_values[actor] = power
                tag = a_state.get("tag")
                if tag is not None:
                    tag_sums[tag] += power

            storage_state = state.get("storage_state", {}) or {}
            policy_state = state.get("policy_state", {}) or {}

            mg = self.microgrids.get(mg_name)
            coords = mg.coords if mg and hasattr(mg, 'coords') else None

            self._influx_writer.write_batch(
                t,
                actor_values,
                microgrid=mg_name,
                sim_id=self.sim_id,
                soc=storage_state.get("soc"),
                p_grid=state.get("p_grid"),
                p_delta=state.get("p_delta"),
                coords=coords,
                capacity=storage_state.get("capacity"),
                charge_level=storage_state.get("charge_level"),
                charge_power=policy_state.get("charge_power"),
                min_soc=storage_state.get("min_soc"),
                c_rate=storage_state.get("c_rate"),
                mode=policy_state.get("mode"),
                tag_sums=dict(tag_sums) if tag_sums else None,
            )

    def finalize(self) -> None:
        if self._influx_writer is not None:
            self._influx_writer.close()
            print(f"Monitor: {self._influx_writer.points_written} points streamed to InfluxDB")


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
        self.requests = requests
        self.broker_port = broker_port
        self.broker_url = f"http://localhost:{broker_port}"
        self.export_prometheus = export_prometheus
        self.microgrids: dict[str, Microgrid] = {}
        self.broker_process: Optional[multiprocessing.Process] = None

    def start(self, microgrids: dict[str, Microgrid]) -> None:
        self.microgrids = microgrids
        self._start_broker()
        for mg_name, mg in microgrids.items():
            config = {
                "name": mg_name,
                "actors": [actor.name for actor in mg.actors],
                "storage": mg.storage.__class__.__name__ if mg.storage else None,
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

                if target == "storage" and mg.storage:
                    setattr(mg.storage, prop, val)
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
                    "storage_state",
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
        microgrids = [key.split(".grid.Grid")[0] for key in data["p_delta"].keys()]
        microgrid_states: dict[str, MicrogridState] = {name: {
            "p_delta": data["p_delta"][f"{name}.grid.Grid"],
            "p_grid": data["p_grid"][f"{name}.storage.Storage"],
            "actor_states": {k.split(".")[-1]: data["actor_states"][k] for k in data["actor_states"].keys() if k.startswith(f"{name}.actor.")},  # noqa: E501
            "policy_state": next((v for k, v in data["policy_state"].items() if k.startswith(f"{name}.storage.Storage")), {}),  # noqa: E501
            "storage_state": next((v for k, v in data.get("storage_state", {}).items() if k.startswith(f"{name}.storage.Storage")), None),  # noqa: E501
            "grid_signals": next((v for k, v in data["grid_signals"].items() if k.startswith(f"{name}.grid.Grid")), None),  # noqa: E501
        } for name in microgrids}

        now = self.clock.to_datetime(time)
        for controller in self.controllers:
            controller.step(now, microgrid_states)

        return time + self.step_size

    def finalize(self) -> None:
        """Stops the api server and the collector thread when the simulation finishes."""
        for controller in self.controllers:
            controller.finalize()
