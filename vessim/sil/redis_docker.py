from time import sleep
from typing import Optional

import docker  # type: ignore
import redis  # type: ignore
from docker.models.containers import Container


class RedisContainer:
    """Class for connection to a Docker container with Redis.

    Args:
        port: Port for connection, defaults to 6379 (Redis default).

    Attributes:
        redis: The redis db that can be used to get and set key, value pairs.
    """

    def __init__(self, docker_client: Optional[docker.DockerClient] = None, port: int = 6379):
        self.docker_container = _init_docker(docker_client, port)
        self.redis = _connect_redis()

    def finalize(self) -> None:
        """Stops the Docker container with Redis when instance is deleted."""
        self.docker_container.stop()


def _connect_redis() -> redis.Redis:
    """Connects to the Redis instance in the Docker container.

    Waits until a connection is established.
    """
    while True:
        try:
            db = redis.Redis()
            if db.ping():
                return db
        except redis.exceptions.RedisError as redis_error:
            print(f"Error connecting to Redis: {redis_error}")
            sleep(1)


def _init_docker(docker_client: Optional[docker.DockerClient], port: int) -> Container:
    """Initializes Docker client and starts Docker container with Redis."""
    if docker_client is None:
        docker_client = docker.from_env()
    redis_container = docker_client.containers.run(
        "redis:latest",
        ports={f"6379/tcp": port},
        detach=True,  # run in background
    )

    # Check if the container has started
    while True:
        container_info = docker_client.containers.get(redis_container.id)
        if container_info.status == "running":
            break
        sleep(1)

    return redis_container
