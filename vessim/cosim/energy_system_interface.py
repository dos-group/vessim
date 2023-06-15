from threading import Thread
from typing import Dict, List, Any, Optional

from fastapi import FastAPI
from fastapi import HTTPException

from lib.http_client import HTTPClient, HTTPClientError
from vessim.core.storage import SimpleBattery, DefaultStoragePolicy
from vessim.cosim._util import VessimSimulator, VessimModel
from vessim.sil.node import Node
from vessim.sil.redis_docker import RedisDocker


class EnergySystemInterfaceSim(VessimSimulator):
    """Virtual Energy System (VES) simulator that executes the VES model."""

    META = {
        "type": "time-based",
        "models": {
            "EnergySystemInterface": {
                "public": True,
                "params": ["battery", "policy", "db_host", "api_host"],
                "attrs": ["battery", "p_cons", "p_gen", "p_grid", "ci"],
            },
        },
    }

    def __init__(self) -> None:
        self.step_size = None
        super().__init__(self.META, _EnergySystemInterfaceModel)

    def init(self, sid, time_resolution, step_size, eid_prefix=None):
        self.step_size = step_size
        super().init(sid, time_resolution, eid_prefix=eid_prefix)

    def finalize(self) -> None:
        """Stops the uvicorn server after the simulation has finished."""
        super().finalize()
        for model_instance in self.entities.values():
            model_instance.redis_docker.stop()

    def next_step(self, time):
        return time + self.step_size


class _EnergySystemInterfaceModel(VessimModel):
    """Software-in-the-Loop interface to the energy system simulation.

    TODO this class is still very specific to our paper use case and does not generalize
        well to other scenarios.

    Args:
        battery: SimpleBatteryModel used by the system.
        policy: The (dis)charging policy used to control the battery.
        nodes: List of physical or virtual computing nodes.
        db_host (optional): The host address for the database, defaults to '127.0.0.1'.
        api_host (optional): The host address for the API, defaults to '127.0.0.1'.
    """

    def __init__(
        self,
        nodes: list[Node],
        battery: SimpleBattery,
        policy: DefaultStoragePolicy,
        db_host: str = "127.0.0.1",
        api_host: str = "127.0.0.1",
    ):
        self.nodes = nodes
        self.battery = battery
        self.policy = policy
        self.p_cons = 0
        self.p_gen = 0
        self.p_grid = 0
        self.ci = 0

        # db & api
        self.redis_docker = RedisDocker(host=db_host)
        f_api = self.init_fastapi()
        self.redis_docker.run(f_api, host=api_host)

    def step(self, time: int, inputs: dict) -> None:
        self.p_cons = inputs["p_cons"]
        self.p_gen = inputs["p_gen"]
        self.ci = inputs["ci"]
        self.p_grid = inputs["p_grid"]

        # update redis
        self.redis_docker.redis.set("solar", self.p_gen)
        self.redis_docker.redis.set("ci", self.ci)

        # get redis update
        self.battery.min_soc = self.redis_get("battery.min_soc")
        self.policy.grid_power = self.redis_get("battery_grid_charge")
        # update power mode for the node remotely
        for node in self.nodes:
            updated_power_mode = self.redis_get("node.power_mode", str(node.id))
            if node.power_mode == updated_power_mode:
                continue
            node.power_mode = updated_power_mode
            http_client = HTTPClient(f"{node.address}:{node.port}")

            def update_power_model():
                try:
                    http_client.put("/power_mode", {"power_mode": node.power_mode})
                except HTTPClientError as e:
                    print(e)
            # use thread to not slow down simulation
            update_thread = Thread(target=update_power_model)
            update_thread.start()

    def init_fastapi(self) -> FastAPI:
        """Initializes the FastAPI application.

        Returns:
            FastAPI: The initialized FastAPI application.
        """
        app = FastAPI()
        self.init_get_routes(app)
        self.init_put_routes(app)
        return app

    def redis_get(self, entry: str, field: Optional[str] = None) -> Any:
        """Method for getting data from Redis database.

        Args:
            entry: The name of the key to retrieve from Redis.
            field: The field (or item_id in your case) to retrieve from the
                hash at the specified key.

        Returns:
            any: The value retrieved from Redis.

        Raises:
            ValueError: If the key or the field does not exist in Redis.
        """
        if self.redis_docker.redis.type(entry) == b'hash' and field is not None:
            value = self.redis_docker.redis.hget(entry, field)
        else:
            value = self.redis_docker.redis.get(entry)

        if value is None:
            if field:
                raise ValueError(f"field {field} does not exist in the hash {entry}")
            else:
                raise ValueError(f"entry {entry} does not exist")
        return value

    def init_get_routes(self, app: FastAPI) -> None:
        """Initializes GET routes for a FastAPI.

        With the given route attributes, the initial values of the attributes
        are stored in Redis key-value store.

        Args:
            app (FastAPI): The FastAPI app to add the GET routes to.
        """
        # store attributes and its initial values in Redis key-value store
        redis_init_content = {
            "solar": self.p_gen,
            "ci": self.ci,
            "battery.soc": self.battery.soc(),
            # TODO implement forecasts:
            #'ci_forecast': self.ci_forecast,
            #'solar_forecast': self.solar_forecast
        }
        self.redis_docker.redis.mset(redis_init_content)

        @app.get("/solar")
        async def get_solar() -> float:
            return self.p_gen

        @app.get("/ci")
        async def get_ci() -> float:
            return self.ci

        @app.get("/battery-soc")
        async def get_battery_soc() -> float:
            return self.battery.soc()

    def init_put_routes(self, app: FastAPI) -> None:
        """Initialize PUT routes for the FastAPI application.

        Two PUT routes are set up: '/ves/battery' to update the battery
        settings, and '/cs/nodes/{item_id}' to update the power mode of a
        specific node. This method handles data validation and updates the
        corresponding attributes in the application instance and Redis
        datastore.

        Args:
            app (FastAPI): FastAPI application instance to which PUT routes are added.
        """

        def validate_keys(data: Dict[str, Any], expected_keys: List[str]):
            missing_keys = set(expected_keys) - set(data.keys())
            if missing_keys:
                raise HTTPException(
                    status_code=422, detail=f"Missing keys: {', '.join(missing_keys)}"
                )

        @app.put("/ves/battery")
        async def put_battery(data: Dict[str, float]):
            validate_keys(data, ["min_soc", "grid_charge"])
            self.redis_docker.redis.set("battery.min_soc", data["min_soc"])
            self.redis_docker.redis.set("battery_grid_charge", data["grid_charge"])
            return data

        @app.put("/cs/nodes/{item_id}")
        async def put_nodes(data: Dict[str, str], item_id: int):
            validate_keys(data, ["power_mode"])
            power_modes = ["power-saving", "normal", "high performance"]
            value = data["power_mode"]
            if value not in power_modes:
                raise HTTPException(
                status_code=400,
                detail=f"{value} is not a valid power mode. "
                f"Available power modes: {power_modes}",
            )
            self.redis_docker.redis.hset("node.power_mode", str(item_id), value)
            return data

    def print_redis(self):
        """Debugging function that simply prints all entries of the redis db."""
        r = self.redis_docker.redis
        # Start the SCAN iterator
        cursor = 0
        while True:
            cursor, keys = r.scan(cursor)
            for key in keys:
                # Check the type of the key
                key_type = r.type(key)

                # Retrieve the value according to the key type
                if key_type == b"string":
                    value = r.get(key)
                elif key_type == b"hash":
                    value = r.hgetall(key)
                elif key_type == b"list":
                    value = r.lrange(key, 0, -1)
                elif key_type == b"set":
                    value = r.smembers(key)
                elif key_type == b"zset":
                    value = r.zrange(key, 0, -1, withscores=True)
                else:
                    value = None

                print(f"Key: {key}, Type: {key_type}, Value: {value}")

            if cursor == 0:
                break
