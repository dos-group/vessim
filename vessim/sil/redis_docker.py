from time import sleep
import docker # type: ignore
import redis # type: ignore


class RedisDocker:
    """Class for connection to a Docker container with Redis.

    Args:
        host: Host address, defaults to '127.0.0.1'.
        port: Port for connection, defaults to 6379 as specified by Redis.

    Attributes:
        redis: The redis db that can be used to get and set key, value pairs.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 6379) -> None:
        self.host = host
        self.port = port
        try:
            self._init_docker()
        except docker.errors.DockerException:
            raise RuntimeError("Please start Docker before execution.")
        self.redis = self._connect_redis()

    def _init_docker(self) -> None:
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

    def _connect_redis(self) -> redis.Redis:
        """Connects to the Redis instance in the Docker container.

        Waits until a connection is established.
        """
        db = None
        connected = False
        while not connected:
            try:
                db = redis.Redis(host=self.host, port=self.port, db=0)
                connected = db.ping()
            except redis.exceptions.RedisError as redis_error:
                print(f"Error connecting to Redis: {redis_error}")
                sleep(1)
        assert db is not None
        return db

    def __del__(self) -> None:
        """Stops the Docker container with Redis when instance is deleted."""
        if self.redis_container:
            self.redis_container.stop()
