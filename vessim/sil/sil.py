import json
import multiprocessing
import pickle
from datetime import datetime
from time import sleep
from collections import defaultdict
from threading import Thread
from typing import Dict, Callable, Optional, List, Any

import docker
import redis
import uvicorn
from docker.models.containers import Container
from fastapi import FastAPI

from vessim import TimeSeriesApi
from vessim.core.power_meter import HttpPowerMeter
from vessim.core.microgrid import Microgrid
from vessim.cosim.controller import Controller
from vessim.cosim.util import Clock
from vessim.sil.http_client import HttpClient


class ComputeNode:  # TODO we could soon replace this agent-based implementation with k8s
    """Represents a physical or virtual computing node.

    This class keeps track of nodes and assigns unique IDs to each new
    instance. It also allows the setting of a power meter and power mode.

    Args:
        name: A unique name assigned to each node.
        address: The network address of the node API.
        port: The application port of the node API.
    """

    def __init__(
        self,
        name: str,
        power_mode: str = "normal",
        address: str = "127.0.0.1",
        port: int = 8000,
    ):
        self.name = name
        self.http_client = HttpClient(f"{address}:{port}")
        self.power_mode = power_mode

    def set_power_mode(self, power_mode: str):
        if power_mode == self.power_mode:
            return

        def update_power_model():
            self.http_client.put("/power_mode", {"power_mode": power_mode})
        Thread(target=update_power_model).start()
        self.power_mode = power_mode


class Broker:
    def __init__(self):
        self.redis_db = redis.Redis()

    def get_microgrid(self) -> Microgrid:
        return pickle.loads(self.redis_db.get("microgrid"))

    def get_actor(self, actor: str) -> Dict:
        return json.loads(self.redis_db.get("actors"))[actor]

    def get_grid_power(self) -> float:
        return float(self.redis_db.get("p_delta"))

    def set_event(self, category: str, value: Any) -> None:
        self.redis_db.lpush("set_events", pickle.dumps(dict(
            category=category,
            time=datetime.now(),
            value=value,
        )))


class SilController(Controller):

    def __init__(
        self,
        step_size: int,
        api_routes: Callable,
        request_collectors: Dict[str, Callable],
        compute_nodes: List[ComputeNode],
        api_host: str = "127.0.0.1",
        api_port: int = 8000,
        request_collector_interval: float = 1,
    ):
        super().__init__(step_size=step_size)
        self.api_routes = api_routes
        self.request_collectors = request_collectors
        self.compute_nodes_dict = {n.name: n for n in compute_nodes}
        self.api_host = api_host
        self.api_port = api_port
        self.request_collector_interval = request_collector_interval
        self.redis_docker_container = _redis_docker_container()
        self.redis_db = redis.Redis()

        self.microgrid = None
        self.clock = None
        self.grid_signals = None
        self.api_server_process = None

    def start(self, microgrid: Microgrid, clock: Clock, grid_signals: Dict):
        self.microgrid = microgrid
        self.clock = clock
        self.grid_signals = grid_signals

        self.api_server_process = multiprocessing.Process(  # TODO logging
            target=_serve_api,
            name="Vessim API",
            daemon=True,
            kwargs=dict(
                api_routes=self.api_routes,
                api_host=self.api_host,
                api_port=self.api_port,
                grid_signals=grid_signals,
            )
        )
        self.api_server_process.start()

        Thread(target=self._collect_set_requests_loop, daemon=True).start()

    def step(self, time: int, p_delta: float, actors: Dict) -> None:
        pipe = self.redis_db.pipeline()
        pipe.set("time", time)
        pipe.set("p_delta", p_delta)
        pipe.set("actors", json.dumps(actors))
        pipe.set("microgrid", self.microgrid.pickle())
        pipe.execute()

    def finalize(self) -> None:
        print("Shutting down Redis...")  # TODO logging
        if self.redis_docker_container is not None:
            self.redis_docker_container.stop()

    def _collect_set_requests_loop(self):
        while True:
            events = self.redis_db.lrange("set_events", start=0, end=-1)
            if len(events) > 0:
                events = [pickle.loads(e) for e in events]
                events_by_category = defaultdict(dict)
                for event in events:
                    events_by_category[event["category"]][event["time"]] = event["value"]
                for category, events in events_by_category.items():
                    self.request_collectors[category](
                        events=events_by_category[category],
                        microgrid=self.microgrid,
                        compute_nodes=self.compute_nodes_dict,
                    )
            self.redis_db.delete("set_events")
            sleep(self.request_collector_interval)


def _serve_api(
    api_routes: Callable,
    api_host: str,
    api_port: int,
    grid_signals: Dict[str, TimeSeriesApi],
):
    print("Starting API server...")
    app = FastAPI()
    api_routes(app, Broker(), grid_signals)
    config = uvicorn.Config(app=app, host=api_host, port=api_port, access_log=False)
    server = uvicorn.Server(config=config)
    server.run()


def _redis_docker_container(
    docker_client: Optional[docker.DockerClient] = None,
    port: int = 6379
) -> Container:
    """Initializes Docker client and starts Docker container with Redis."""
    if docker_client is None:
        try:
            docker_client = docker.from_env()
        except docker.errors.DockerException as e:
            raise RuntimeError("Could not connect to Docker.") from e
    container = docker_client.containers.run(
        "redis:latest",
        ports={f"6379/tcp": port},
        detach=True,  # run in background
    )

    # Check if the container has started
    while True:
        container_info = docker_client.containers.get(container.name)
        if container_info.status == "running":
            break
        sleep(1)

    return container


def latest_event(events: Dict[datetime, Any]) -> Any:
    return events[max(events.keys())]
