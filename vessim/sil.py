"""Vessim Software-in-the-Loop (SiL) components.

This module is still experimental, the public API might change at any time.
"""

import json
import multiprocessing
import pickle
import time
from collections import defaultdict
from datetime import datetime
from threading import Thread
from time import sleep
from typing import Dict, Callable, Optional, List, Any

import docker
import redis
import uvicorn
from docker.models.containers import Container
from fastapi import FastAPI

from vessim._util import HttpClient
from vessim.core import TimeSeriesApi
from vessim.cosim import Controller, PowerMeter
from vessim.cosim.environment import Microgrid


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
        """Sets the power mode of the compute node.

        Initiates a change in the power mode settings for the node by sending an
        update to the node's API. This operation may happen asynchronously.

        Args:
            power_mode: A string representing the desired power mode to set for
                the compute node.
        """
        if power_mode == self.power_mode:
            return

        def update_power_model():
            self.http_client.put("/power_mode", {"power_mode": power_mode})
        Thread(target=update_power_model).start()
        self.power_mode = power_mode


class Broker:
    """Manages Redis database for microgrid sim data storage and retrieval.

    This class serves as a bridge between the simulation components and the
    Redis database, providing an interface to store and fetch data like the
    state of the microgrid, actors, grid power, and events.
    """
    def __init__(self):
        self.redis_db = redis.Redis()

    def get_microgrid(self) -> Microgrid:
        """Fetches the serialized microgrid state from Redis.

        Returns:
            A Microgrid instance that represents the current microgrid state.
        """
        return pickle.loads(self.redis_db.get("microgrid"))

    def get_actor(self, actor: str) -> Dict:
        """Retrieves the state of a specified actor from Redis.

        Args:
            actor: The name of the actor for which to retrieve the state.

        Returns:
            A dictionary representing the state of the specified actor.
        """
        return json.loads(self.redis_db.get("actors"))[actor]

    def get_grid_power(self) -> float:
        """Retrieves the current value of grid power from Redis.

        Returns:
            A floating-point value representing the current grid power.
        """
        return float(self.redis_db.get("p_delta"))

    def set_event(self, category: str, value: Any) -> None:
        """Stores an event in Redis under the given category.

        Args:
            category: The category under which to store the event.
            value: The value of the event to be stored.
        """
        self.redis_db.lpush("set_events", pickle.dumps(dict(
            category=category,
            time=datetime.now(),
            value=value,
        )))


class SilController(Controller):
    """Controls the orchestration of SiL environment interactions and timing.

    This subclass of Controller is designed to manage the simulation loop,
    handle set events, and interface with the API server for the simulation. It
    manages the communication between the SiL components and the compute nodes
    within the simulation environment.

    Args:
        step_size: The time step size for simulation (in seconds).
        api_routes: The function to define the API server's routes.
        request_collectors: A dictionary mapping each request category to a
            callable that will handle the requests periodically.
        compute_nodes: A list of ComputeNode instances representing available
            compute resources.
        api_host: The host IP for the API server. Defaults to '127.0.0.1'.
        api_port: The port number for the API server. Defaults to '8000'.
        request_collector_interval: The time interval between collections of
            requests for the compute nodes. Defaults to '1'.

    Raises:
        RuntimeError: If there is an issue connecting with the Docker
            environment when setting up the Redis Docker container.
    """

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

    def custom_init(self):
        """Initializes the API server and begins the request collection loop.

        This method configures and starts a separate process for the API server,
        initializes a thread to handle incoming 'set' requests, and sets up any
        necessary infrastructure for the simulation to run.
        """
        self.api_server_process = multiprocessing.Process(  # TODO logging
            target=_serve_api,
            name="Vessim API",
            daemon=True,
            kwargs=dict(
                api_routes=self.api_routes,
                api_host=self.api_host,
                api_port=self.api_port,
                grid_signals=self.grid_signals,
            )
        )
        self.api_server_process.start()
        Thread(target=self._collect_set_requests_loop, daemon=True).start()

    def step(self, time: int, p_delta: float, actors: Dict) -> None:
        """Advances the simulation by one time step.

        This method is called during each time step of the simulation. It
        updates the shared state in the Redis database to reflect changes in
        simulation data such as time, power delta, and actor states.

        Args:
            time: The current simulation time.
            p_delta: The change in power since the last step.
            actors: The current state of actors within the simulation.
        """
        pipe = self.redis_db.pipeline()
        pipe.set("time", time)
        pipe.set("p_delta", p_delta)
        pipe.set("actors", json.dumps(actors))
        pipe.set("microgrid", self.microgrid.pickle())
        pipe.execute()

    def finalize(self) -> None:
        """Cleans up resources related to the simulation.

        This method handles the graceful shutdown of the Redis service and stops
        any related Docker containers that were started by this controller.
        """
        print("Shutting down Redis...")  # TODO logging
        if self.redis_docker_container is not None:
            self.redis_docker_container.stop()

    def _collect_set_requests_loop(self):
        """Continuously collects and processes 'set' requests from Redis queue.

        This method runs in a separate thread and is responsible for handling
        events pushed to the Redis queue, categorizing them, and invoking the
        appropriate request collector functions.
        """
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
    """Starts an API server for handling requests related to the simulation.

    This function configures and starts a FastAPI server, which serves as the
    interface for external interaction with the SiL simulation.

    Args:
        api_routes: A callable that is responsible for setting up routes on the
            API server.
        api_host: The host IP address for the API server.
        api_port: The port number for the API server.
        grid_signals: A dictionary containing time series APIs for grid signal
            handling.
    """
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
    """Starts a Redis container using Docker and returns the container object.

    This function will use a provided Docker client or attempt to create one
    from the environment. It then starts a new Docker container running the
    Redis server on the specified port.

    Args:
        docker_client: An optional docker.DockerClient instance that will be
            used to run the Redis container. If not provided, a new client will
            be created by calling docker.from_env().
        port: The port number on the localhost that will be forwarded to the
            Redis container.

    Returns:
        A docker.models.containers.Container instance representing the running
            Redis container.

    Raises:
        RuntimeError: If the function cannot connect to Docker due to an error
            with docker.from_env() or other Docker-related issues.
    """
    if docker_client is None:
        try:
            docker_client = docker.from_env()
        except docker.errors.DockerException as e:
            raise RuntimeError("Could not connect to Docker.") from e
    container = docker_client.containers.run(
        "redis:latest",
        ports={"6379/tcp": port},
        detach=True,  # run in background
    )

    # Check if the container has started
    while True:
        container_info = docker_client.containers.get(container.name)
        if container_info.status == "running":
            break
        sleep(1)

    return container


def get_latest_event(events: Dict[datetime, Any]) -> Any:
    """Retrieves the most recent event based on timestamp.

    Determines the most recent event from a dictionary of events keyed by
    their respective timestamps and returns the associated event's value.

    Args:
        events: A dictionary mapping timestamps (datetime objects) to events.

    Returns:
        The value of the latest event.
    """
    return events[max(events.keys())]


class HttpPowerMeter(PowerMeter):
    """Represents a power meter accessible over HTTP.

    This class extends the PowerMeter base class allowing for power measurement
    retrieval via an HTTP API. It continuously polls the API server at a
    specified interval to update the power value.

    Args:
        name: The unique identifier for the power meter.
        address: The IP address or hostname of the API server.
        port: The port number of the API server. Defaults to 8000.
        collect_interval: The frequency in seconds to collect power data.
            Defaults to 1 second.
    """

    def __init__(
        self,
        name: str,
        address: str,
        port: int = 8000,
        collect_interval: float = 1,
    ) -> None:
        super().__init__(name)
        self.http_client = HttpClient(f"{address}:{port}")
        self.collect_interval = collect_interval
        self._p = 0.0
        Thread(target=self._collect_loop, daemon=True).start()

    def measure(self) -> float:
        """Obtains the current power measurement.

        Returns:
            The last collected power measurement as a floating-point number.
        """
        return self._p

    def _collect_loop(self) -> None:
        """Gets the power demand every `interval` seconds from the API server."""
        while True:
            self._p = float(self.http_client.get("/power")["power"])
            time.sleep(self.collect_interval)
