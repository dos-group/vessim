import docker
from time import sleep

import redis
from fastapi import FastAPI
from redis import Redis
import threading
import uvicorn


class RedisDocker:
    """Class for connection to a Docker container with Redis.

    Attributes:
        redis: The redis db that can be used to get and set key, value pairs.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 6379) -> None:
        """Initialization of container with Redis and connection to it.

        After instantiation, run() needs to be called with a FastAPI instance.

        Args:
            host: Host address, defaults to '127.0.0.1'.
            port: Port for connection, defaults to 6379 as specified by Redis.
        """
        self.host = host
        self.port = port
        try:
            self.init_docker()
        except docker.errors.DockerException:
            raise RuntimeError("Please start Docker before execution.")
        self.redis = self.connect_redis()

    def init_docker(self) -> None:
        """Initializes Docker client and starts Docker container with Redis."""
        client = docker.from_env()
        self.redis_container = client.containers.run(
            "redis:latest",
            auto_remove=True,
            ports={f"{self.port}/tcp": self.port},
            detach=True,
        )

        # Check if the container has started
        while True:
            container_info = client.containers.get(self.redis_container.id)
            if container_info.status == "running":
                break
            sleep(1)

    def connect_redis(self) -> Redis:
        """Connects to the Redis instance in the Docker container.

        Waits until a connection is established.
        """
        db = None
        connected = False
        while not connected:
            try:
                db = Redis(host=self.host, port=self.port, db=0)
                connected = db.ping()
            except redis.exceptions.RedisError as redis_error:
                print(f"Error connecting to Redis: {redis_error}")
                sleep(1)
        assert db is not None
        return db

    def run(self, f_api: FastAPI, host: str = "127.0.0.1", port: int = 8000) -> None:
        """Starts the given FastAPI application.

        Runs FastAPI with a uvicorn server in a seperate thread
        and waits until it finished startup.

        Args:
            f_api: FastAPI, the FastAPI application to run
            host: The host address, defaults to '127.0.0.1'.
            port: The port to run the FastAPI application, defaults to 8000.
        """
        self.server_thread = ServerThread(f_api, host, port)
        self.server_thread.start()
        self.server_thread.wait_for_startup_complete()

    def stop(self):
        """Stops the FastAPI uvicorn server thread."""
        self.server_thread.stop()

    def __del__(self) -> None:
        """Stops the Docker container with Redis wheninstance is deleted."""
        if hasattr(self, "redis_container"):
            self.redis_container.stop()


class ServerThread(threading.Thread):
    """Thread that runs a given FastAPI application with a uvicorn server."""

    def __init__(self, f_api: FastAPI, host: str, port: int) -> None:
        """Initializes the Thread with the FastAPI.

        Args:
            f_api: FastAPI, the FastAPI application to run
            host: The host address, defaults to '127.0.0.1'.
            port: The port to run the FastAPI application, defaults to 8000.
        """
        super().__init__()
        config = uvicorn.Config(app=f_api, host=host, port=port)
        self.server = uvicorn.Server(config=config)
        self.startup_complete = False

        @f_api.on_event("startup")
        async def startup_event():
            self.startup_complete = True

    def wait_for_startup_complete(self):
        """Waiting for completion of startup process.

        To ensure the server is operational for the simulation, the startup
        needs to complete before any requests can be made. Waits for the
        uvicorn server to finish startup.
        """
        while not self.startup_complete:
            sleep(1)

    def run(self):
        """Called when the thread is started. Runs the uvicorn server."""
        self.server.run()

    def stop(self):
        """Stops the uvicorn server.

        Mosaik does not stop the server on its own after the simulation has
        finished. Gracefully stops the uvicorn server.
        """
        self.server.should_exit = True
