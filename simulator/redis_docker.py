import docker
from time import sleep
from fastapi import FastAPI
from redis import Redis
import uvicorn


class RedisDocker:
    """
    Initializes a a Docker container with Redis and connects to it. After
    instantiation, run() needs to be called with a FastAPI instance.

    Args:
        host: The host address, defaults to '127.0.0.1'.
        port: The port to connect to Redis, defaults to 6379 as specified by Redis.

    Attributes:
        redis: The redis db that can be used to get and set key, value pairs.
    """

    def __init__(self, host: str = '127.0.0.1', port: int = 6379) -> None:
        self.host = host
        self.port = port
        self.redis = self.init_docker()
        self.connect_redis()

    def init_docker(self) -> None:
        """
        Initializes a Docker client and starts a Docker container with Redis.
        """
        client = docker.from_env()
        self.redis_container = client.containers.run(
            'redis:latest',
            auto_remove=True,
            ports={f'{self.port}/tcp': self.port},
            detach=True
        )

    def connect_redis(self) -> Redis:
        """
        Connects to the Redis instance running in the Docker container.
        Waits until a connection is established.
        """
        redis = None
        connected = False
        while not connected:
            try:
                redis = Redis(host=self.host, port=self.port, db=0)
                connected = redis.ping()
            except:
                sleep(1)
        assert redis != None
        return redis

    def run(self, f_api: FastAPI, host: str = '127.0.0.1', port: int = 8000) -> None:
        """
        Runs the given FastAPI application.

        Args:
            f_api: FastAPI, the FastAPI application to run
            host: The host address, defaults to '127.0.0.1'.
            port: The port to run the FastAPI application, defaults to 8000.
        """
        uvicorn.run(f_api, host=host, port=port)

    def __del__(self) -> None:
        """
        Stops the Docker container with Redis when the instance is deleted.
        """
        self.redis_container.stop()
