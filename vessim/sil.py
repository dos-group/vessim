"""Vessim Software-in-the-Loop (SiL) components.

This module is still experimental, the public API might change at any time.
"""

from __future__ import annotations

import json
import multiprocessing
import pickle
from collections import defaultdict
from datetime import datetime, timedelta
from threading import Thread
from time import sleep
from typing import Any, Optional, Callable

import docker  # type: ignore
import pandas as pd
import redis
import requests
import uvicorn
from docker.models.containers import Container  # type: ignore
from fastapi import FastAPI
from loguru import logger
from requests.auth import HTTPBasicAuth

from vessim.cosim import Controller, Microgrid
from vessim.signal import Signal
from vessim.util import DatetimeLike, Clock


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
        return pickle.loads(self.redis_db.get("microgrid"))  # type: ignore

    def get_actor(self, actor: str) -> dict:
        return json.loads(self.redis_db.get("actors"))[actor]  # type: ignore

    def get_grid_power(self) -> float:
        return float(self.redis_db.get("p_delta"))  # type: ignore

    def set_event(self, category: str, value: Any) -> None:
        self.redis_db.lpush(
            "set_events",
            pickle.dumps(
                dict(
                    category=category,
                    time=datetime.now(),
                    value=value,
                )
            ),
        )


class SilController(Controller):
    def __init__(
        self,
        api_routes: Callable,
        request_collectors: Optional[dict[str, Callable]] = None,
        compute_nodes: Optional[list[ComputeNode]] = None,
        api_host: str = "127.0.0.1",
        api_port: int = 8000,
        request_collector_interval: float = 1,
        step_size: Optional[int] = None,
    ):
        super().__init__(step_size=step_size)
        self.api_routes = api_routes
        self.request_collectors = (
            request_collectors if request_collectors is not None else {}
        )
        self.compute_nodes_dict = (
            {n.name: n for n in compute_nodes} if compute_nodes is not None else {}
        )
        self.api_host = api_host
        self.api_port = api_port
        self.request_collector_interval = request_collector_interval
        self.redis_docker_container = _redis_docker_container()
        self.redis_db = redis.Redis()

        self.microgrid: Optional[Microgrid] = None
        self.clock: Optional[Clock] = None
        self.grid_signals: Optional[dict] = None

    def start(self, microgrid: Microgrid, clock: Clock, grid_signals: dict) -> None:
        self.microgrid = microgrid
        self.clock = clock
        self.grid_signals = grid_signals

        multiprocessing.Process(
            target=_serve_api,
            name="Vessim API",
            daemon=True,
            kwargs=dict(
                api_routes=self.api_routes,
                api_host=self.api_host,
                api_port=self.api_port,
                grid_signals=self.grid_signals,
            ),
        ).start()
        logger.info("Started SiL Controller API server process 'Vessim API'")

        Thread(target=self._collect_set_requests_loop, daemon=True).start()

    def step(self, time: int, p_delta: float, actor_infos: dict) -> None:
        pipe = self.redis_db.pipeline()
        pipe.set("time", time)
        pipe.set("p_delta", p_delta)
        pipe.set("actors", json.dumps(actor_infos))
        assert self.microgrid is not None
        pipe.set("microgrid", self.microgrid.pickle())
        pipe.execute()

    def finalize(self) -> None:
        if self.redis_docker_container is not None:
            self.redis_docker_container.stop()
        logger.info("Shut down Redis docker container")

    def _collect_set_requests_loop(self):
        while True:
            events = self.redis_db.lrange("set_events", start=0, end=-1)
            assert events is not None
            if len(events) > 0: # type: ignore
                events = [pickle.loads(e) for e in events] # type: ignore
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
    grid_signals: dict[str, Signal],
):
    app = FastAPI()
    api_routes(app, Broker(), grid_signals)
    config = uvicorn.Config(app=app, host=api_host, port=api_port, access_log=False)
    server = uvicorn.Server(config=config)
    server.run()


def _redis_docker_container(
    docker_client: Optional[docker.DockerClient] = None, port: int = 6379
) -> Container:
    """Initializes Docker client and starts Docker container with Redis."""
    if docker_client is None:
        try:
            docker_client = docker.from_env()
        except docker.errors.DockerException as e: # type: ignore
            raise RuntimeError("Could not connect to Docker.") from e
    try:
        container = docker_client.containers.run(
            "redis:latest",
            ports={"6379/tcp": port},
            detach=True,  # run in background
        )
    except docker.errors.APIError as e: # type: ignore
        if e.status_code == 500 and "port is already allocated" in e.explanation:
            # TODO prompt user to automatically kill container
            raise RuntimeError(
                f"Could not start Redis container as port {port} is "
                f"already allocated. Probably a prevois execution was not "
                f"cleaned up properly by Vessim."
            ) from e
        raise

    # Check if the container has started
    while True:
        container_info = docker_client.containers.get(container.name) # type: ignore
        if container_info.status == "running": # type: ignore
            break
        sleep(1)

    return container # type: ignore


def get_latest_event(events: dict[datetime, Any]) -> Any:
    return events[max(events.keys())]


class WatttimeSignal(Signal):
    _URL = "https://api.watttime.org"

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.headers = {"Authorization": f"Bearer {self._login()}"}

    def at(
        self,
        dt: DatetimeLike,
        region: Optional[str] = None,
        signal_type: str = "co2_moer",
        **kwargs,
    ):
        if region is None:
            raise ValueError("Region needs to be specified.")
        dt = pd.to_datetime(dt)
        rsp = self._request(
            "/historical",
            params={
                "region": region,
                "start": (dt - timedelta(minutes=5)).isoformat(),
                "end": dt.isoformat(),
                "signal_type": signal_type,
            },
        )
        return rsp

    def _request(self, endpoint: str, params: dict):
        while True:
            rsp = requests.get(
                f"{self._URL}/v3{endpoint}", headers=self.headers, params=params
            )
            if rsp.status_code == 200:
                return rsp.json()["data"][0]["value"]
            if rsp.status_code == 400:
                return f"Error {rsp.status_code}: {rsp.json()}"
            elif rsp.status_code in [401, 403]:
                print("Renewing authorization with Watttime API.")
                self.headers["Authorization"] = f"Bearer {self._login()}"
            else:
                raise ValueError(f"Error {rsp.status_code}: {rsp}")

    def _login(self) -> str:
        # TODO reconnect if token is expired
        rsp = requests.get(
            f"{self._URL}/login", auth=HTTPBasicAuth(self.username, self.password)
        )
        return rsp.json()["token"]


class HttpClient:
    """Class for making HTTP requests to the Vessim API server.

    Args:
        server_address: The address of the server to connect to.
            e.g. http://localhost
    """

    def __init__(self, server_address: str, timeout: float = 5) -> None:
        self.server_address = server_address
        self.timeout = timeout

    def get(self, route: str) -> dict:
        """Sends a GET request to the server and retrieves data.

        Args:
            route: The path of the endpoint to send the request to.

        Raises:
            HTTPError: If response code is != 200.

        Returns:
            A dictionary containing the response.
        """
        response = requests.get(self.server_address + route, timeout=self.timeout)
        if response.status_code != 200:
            response.raise_for_status()
        data = response.json()  # assuming the response data is in JSON format
        return data

    def put(self, route: str, data: dict[str, Any] = {}) -> None:
        """Sends a PUT request to the server to update data.

        Args:
            route: The path of the endpoint to send the request to.
            data: The data to be updated, in dictionary format.

        Raises:
            HTTPError: If response code is != 200.
        """
        headers = {"Content-type": "application/json"}
        response = requests.put(
            self.server_address + route,
            data=json.dumps(data),
            headers=headers,
            timeout=self.timeout,
        )
        if response.status_code != 200:
            response.raise_for_status()
