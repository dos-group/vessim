from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from csv import DictWriter, QUOTE_ALL
from itertools import count
from collections.abc import Iterator
from typing import Any, Optional, TYPE_CHECKING
import multiprocessing
import time

import mosaik_api_v3  # type: ignore
import requests  # Used in Monitor.finalize


# --- DEFAULTS FOR INFLUXDB 2 ---
INFLUX_URL = "http://127.0.0.1:8086"
INFLUX_ORG = "vessim_org"
INFLUX_BUCKET = "vessim_bucket"
INFLUX_TOKEN = "supersecrettoken"

if TYPE_CHECKING:
    from vessim.microgrid import Microgrid, MicrogridState


# =============================================================================
# BASE CONTROLLER
# =============================================================================

class Controller(ABC):
    _counters: dict[type["Controller"], Iterator[int]] = {}

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        cls._counters[cls] = count()

    def __init__(self, microgrids: list["Microgrid"], step_size: Optional[int] = None) -> None:
        cls = self.__class__
        self.name: str = f"{cls.__name__}-{next(cls._counters[cls])}"
        self.microgrids: dict[str, "Microgrid"] = {mg.name: mg for mg in microgrids}
        self.step_size = step_size
        self.set_parameters: dict[str, Any] = {}

    @abstractmethod
    def step(self, time: datetime, microgrid_states: dict[str, "MicrogridState"]) -> None:
        pass

    def finalize(self) -> None:
        pass


# =============================================================================
# MONITOR
# =============================================================================

class Monitor(Controller):
    def __init__(
        self,
        microgrids: list["Microgrid"],
        step_size: Optional[int] = None,
        outfile: Optional[str | Path] = None,
        influx_url: Optional[str] = None,
        influx_bucket: Optional[str] = None,
        influx_token: Optional[str] = None,
        influx_org: Optional[str] = None,
    ):
        super().__init__(microgrids, step_size=step_size)

        self.outfile = Path(outfile) if outfile else None
        self.log: dict[datetime, dict[str, "MicrogridState"]] = defaultdict(dict)

        # Single CSV file, stable schema (union header), rewrite-on-schema-change.
        self._csv_fieldnames: list[str] = []
        self._csv_rows: list[dict[str, Any]] = []

        # Influx config
        self.influx_url = influx_url or INFLUX_URL
        self.influx_bucket = influx_bucket or INFLUX_BUCKET
        self.influx_token = influx_token or INFLUX_TOKEN
        self.influx_org = influx_org or INFLUX_ORG

    # ---------------- CSV Logging -------------------

    def step(self, t: datetime, microgrid_states: dict[str, "MicrogridState"]) -> None:
        self.log[t] = microgrid_states
        if self.outfile is not None:
            self._write_microgrid_csv(t, microgrid_states, self.outfile)

    def _write_microgrid_csv(
        self,
        time: datetime,
        microgrid_states: dict[str, "MicrogridState"],
        outfile: Path,
    ) -> None:
        outfile.parent.mkdir(parents=True, exist_ok=True)

        new_rows: list[dict[str, Any]] = []
        for mg_name, state in microgrid_states.items():
            mg = self.microgrids.get(mg_name)
            coords = {}
            if mg and mg.coords:
                coords = {"latitude": mg.coords[0], "longitude": mg.coords[1]}

            # Calculate tag sums
            tag_sums: dict[str, float] = defaultdict(float)
            if "actor_states" in state:
                for actor_state in state["actor_states"].values():
                    tag = actor_state.get("tag")
                    p = actor_state.get("p")
                    if tag is not None and p is not None:
                        tag_sums[tag] += p

            tag_entries = {f"tag_sum.{tag}": value for tag, value in tag_sums.items()}

            entry = {
                "microgrid": mg_name,
                "time": time.isoformat(),
                "latitude": coords.get("latitude"),
                "longitude": coords.get("longitude"),
                **_flatten_dict(dict(state)),
                **tag_entries,
            }
            new_rows.append(entry)

        new_keys = set().union(*(r.keys() for r in new_rows))
        old_keys = set(self._csv_fieldnames)

        schema_changed = not old_keys.issuperset(new_keys)
        self._csv_rows.extend(new_rows)

        if schema_changed or not self._csv_fieldnames:
            missing = sorted(new_keys - old_keys)
            self._csv_fieldnames.extend(missing)
            self._rewrite_full_csv(outfile)
            return

        with outfile.open("a", newline="", encoding="utf-8") as f:
            writer = DictWriter(
                f,
                fieldnames=self._csv_fieldnames,
                extrasaction="ignore",
                quoting=QUOTE_ALL,
            )
            for r in new_rows:
                writer.writerow(_fill_missing(r, self._csv_fieldnames))

    def _rewrite_full_csv(self, outfile: Path) -> None:
        base = ["microgrid", "time", "latitude", "longitude"]
        rest = [c for c in self._csv_fieldnames if c not in base]
        self._csv_fieldnames = base + rest

        with outfile.open("w", newline="", encoding="utf-8") as f:
            writer = DictWriter(
                f,
                fieldnames=self._csv_fieldnames,
                extrasaction="ignore",
                quoting=QUOTE_ALL,
            )
            writer.writeheader()
            for r in self._csv_rows:
                writer.writerow(_fill_missing(r, self._csv_fieldnames))

    # ---------------- InfluxDB Export -------------------

    def finalize(self) -> None:
        super().finalize()

        if not (self.influx_url and self.influx_bucket and self.influx_token and self.influx_org):
            print("Monitor: InfluxDB config missing → skipping export")
            return

        lines: list[str] = []

        for t, states in self.log.items():
            ts = int(t.replace(tzinfo=timezone.utc).timestamp() * 1e9)

            for mg_name, state in states.items():
                actor_states = state.get("actor_states", {}) or {}
                policy_state = state.get("policy_state", {}) or {}
                storage_state = state.get("storage_state", {}) or {}

                p_grid = state.get("p_grid")
                p_delta = state.get("p_delta")

                mg = self.microgrids.get(mg_name)
                lat, lon = None, None
                if mg and mg.coords:
                    lat, lon = mg.coords

                tags = [
                    f"microgrid={mg_name}",
                    f"grid_status={policy_state.get('mode', 'unknown')}",
                ]
                if actor_states:
                    tags.append("actors=" + "_".join(sorted(actor_states.keys())))

                fields: list[str] = []

                # --- Coordinates written to Influx as numeric fields ---
                if isinstance(lat, (int, float)):
                    fields.append(f"latitude={float(lat)}")
                if isinstance(lon, (int, float)):
                    fields.append(f"longitude={float(lon)}")

                # Generic actor powers (added to microgrid point)
                for actor_name, a in actor_states.items():
                    p = a.get("p")
                    if isinstance(p, (int, float)):
                        safe = actor_name.replace(" ", "_")
                        fields.append(f"power_{safe}={float(p)}")
                    
                    # Generate separate point for actor if it has coordinates
                    act_coords = a.get("coords")
                    if act_coords and "latitude" in act_coords and "longitude" in act_coords:
                         act_tags = [f"microgrid={mg_name}", f"actor={actor_name}"]
                         act_fields = [
                            f"p={float(p)}" if isinstance(p, (int, float)) else "",
                            f"latitude={float(act_coords['latitude'])}",
                            f"longitude={float(act_coords['longitude'])}"
                         ]
                         # Filter out empty fields (e.g. if p was None)
                         act_fields = [f for f in act_fields if f]
                         
                         if act_fields:
                             # Use same measurement 'vessim' but with actor tag
                             lines.append(f"vessim,{','.join(act_tags)} {','.join(act_fields)} {ts}")

                # Tag sums
                tag_sums: dict[str, float] = defaultdict(float)
                for a in actor_states.values():
                    tag = a.get("tag")
                    p = a.get("p")
                    if tag is not None and isinstance(p, (int, float)):
                        tag_sums[tag] += p
                
                for tag, value in tag_sums.items():
                     fields.append(f"tag_sum_{tag}={float(value)}")

                # Storage values
                if isinstance(storage_state.get("soc"), (int, float)):
                    fields.append(f"soc={float(storage_state['soc'])}")

                if isinstance(storage_state.get("capacity"), (int, float)):
                    fields.append(f"energy={float(storage_state['capacity'])}")

                # Grid values
                if isinstance(p_grid, (int, float)):
                    fields.append(f"p_grid={float(p_grid)}")

                if isinstance(p_delta, (int, float)):
                    fields.append(f"p_delta={float(p_delta)}")

                if not fields:
                    continue

                line = f"vessim,{','.join(tags)} {','.join(fields)} {ts}"
                lines.append(line)

        if not lines:
            print("Monitor: No data to export")
            return

        payload = "\n".join(lines)
        url = f"{self.influx_url}/api/v2/write"

        r = requests.post(
            url,
            params={"bucket": self.influx_bucket, "org": self.influx_org, "precision": "ns"},
            headers={"Authorization": f"Token {self.influx_token}", "Content-Type": "text/plain"},
            data=payload,
        )

        if r.status_code == 204:
            print(f"Monitor: {len(lines)} points written to InfluxDB")
        else:
            print(f"Monitor: InfluxDB error {r.status_code}: {r.text}")


# =============================================================================
# REST API Controller
# =============================================================================

class Api(Controller):
    def __init__(
        self,
        microgrids: list["Microgrid"],
        step_size: Optional[int] = None,
        export_prometheus: bool = False,
        broker_port: int = 8700,
    ):
        import requests as req
        self.requests = req

        super().__init__(microgrids, step_size=step_size)

        self.broker_port = broker_port
        self.broker_url = f"http://localhost:{broker_port}"
        self.export_prometheus = export_prometheus
        self.broker_process = None

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
        time.sleep(1)

        print(f"API running at {self.broker_url}")

    def _register_microgrids(self):
        for name, mg in self.microgrids.items():
            cfg = {
                "name": name,
                "actors": [a.name for a in mg.actors],
                "storage": mg.storage.__class__.__name__ if mg.storage else None,
            }
            self.requests.post(f"{self.broker_url}/internal/microgrids/{name}", json=cfg)

    def step(self, time: datetime, microgrid_states: dict[str, "MicrogridState"]) -> None:
        self._process_commands()

        for mg_name, mg_state in microgrid_states.items():
            self.requests.post(
                f"{self.broker_url}/internal/data/{mg_name}",
                json={"microgrid": mg_name, "time": time.isoformat(), **mg_state},
            )

    def _process_commands(self):
        res = self.requests.get(f"{self.broker_url}/internal/commands")
        cmds = res.json().get("commands", [])

        for cmd in cmds:
            if cmd.get("type") == "set_parameter":
                mg = cmd.get("microgrid")
                param = cmd.get("parameter")
                value = cmd.get("value")

                if mg and param:
                    key = f"{mg}:{param}"
                    self.set_parameters[key] = value

    def finalize(self) -> None:
        if self.broker_process and self.broker_process.is_alive():
            self.broker_process.terminate()
            self.broker_process.join()


# =============================================================================
# MOSAIK SIM WRAPPER
# =============================================================================

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
        self.controller = None
        self.microgrid_names = []
        self.step_size = None
        self.clock = None
        self.set_parameters: dict[str, Any] = {}

    def init(self, sid, time_resolution=1.0, **sim_params):
        self.step_size = sim_params["step_size"]
        self.clock = sim_params["clock"]
        return self.meta

    def create(self, num, model, **params):
        assert num == 1
        self.controller = params["controller"]
        self.microgrid_names = params["microgrid_names"]
        return [{"eid": self.eid, "type": model}]

    def step(self, time, inputs, max_advance):
        assert self.controller and self.clock and self.step_size

        data = inputs[self.eid]
        microgrids = [
            key.split(".grid.Grid")[0]
            for key in data["p_delta"].keys()
        ]

        states: dict[str, "MicrogridState"] = {
            name: {
                "p_delta": data["p_delta"][f"{name}.grid.Grid"],
                "p_grid": data["p_grid"][f"{name}.storage.Storage"],
                "actor_states": {
                    k.split(".")[-1]: data["actor_states"][k]
                    for k in data["actor_states"].keys()
                    if k.startswith(f"{name}.actor.")
                },
                "policy_state": next(
                    v for k, v in data["policy_state"].items()
                    if k.startswith(f"{name}.storage.Storage")
                ),
                "storage_state": next(
                    v for k, v in data["storage_state"].items()
                    if k.startswith(f"{name}.storage.Storage")
                ),
                "grid_signals": next(
                    v for k, v in data["grid_signals"].items()
                    if k.startswith(f"{name}.grid.Grid")
                ),
            }
            for name in microgrids
        }

        now = self.clock.to_datetime(time)
        self.controller.step(now, states)

        self.set_parameters = self.controller.set_parameters.copy()
        self.controller.set_parameters = {}

        return time + self.step_size

    def get_data(self, outputs):
        return {self.eid: {"set_parameters": self.set_parameters}}

    def finalize(self):
        assert self.controller
        self.controller.finalize()


# =============================================================================
# HELPERS
# =============================================================================

def _get_val(inputs: dict, key: str) -> Any:
    return list(inputs[key].values())[0]


def _flatten_dict(d: dict, parent: str = "") -> dict:
    items: dict[str, Any] = {}
    for k, v in d.items():
        nk = f"{parent}.{k}" if parent else k
        if isinstance(v, dict):
            items.update(_flatten_dict(v, nk))
        else:
            items[nk] = v
    return items


def _fill_missing(row: dict[str, Any], fieldnames: list[str]) -> dict[str, Any]:
    return {k: row.get(k, "") for k in fieldnames}
