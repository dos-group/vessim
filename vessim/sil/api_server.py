import multiprocessing
from time import sleep
from typing import Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from vessim.sil.redis_docker import RedisDocker


class ApiServer(multiprocessing.Process):
    """Process that runs a given FastAPI application with a uvicorn server."""

    def __init__(self, host: str, port: int) -> None:
        """Initializes the Process with the FastAPI.

        Args:
            f_api: FastAPI, the FastAPI application to run
            host: The host address, defaults to '127.0.0.1'.
            port: The port to run the FastAPI application, defaults to 8000.
        """
        super().__init__()
        self.host = host
        self.port = port

        self.redis_docker = RedisDocker(host=host)
        self.f_api = self._init_fastapi()

        self.startup_complete = multiprocessing.Value('b', False)

        @self.f_api.on_event("startup")
        async def startup_event():
            self.startup_complete.value = True

    def wait_for_startup_complete(self):
        """Waiting for completion of startup process.

        To ensure the server is operational for the simulation, the startup
        needs to complete before any requests can be made. Waits for the
        uvicorn server to finish startup.
        """
        while not self.startup_complete:
            sleep(1)

    def run(self):
        """Called when the process is started. Runs the uvicorn server."""
        config = uvicorn.Config(app=self.f_api, host=self.host, port=self.port)
        server = uvicorn.Server(config=config)
        server.run()


    def _init_fastapi(self) -> FastAPI:
        """Initializes the FastAPI application.

        Returns:
            FastAPI: The initialized FastAPI application.
        """
        app = FastAPI()
        self._init_get_routes(app)
        self._init_put_routes(app)
        return app

    def _redis_get(self, entry: str, field: Optional[str] = None) -> Any:
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

    def _init_get_routes(self, app: FastAPI) -> None:
        """Initializes GET routes for a FastAPI.

        Args:
            app: The FastAPI app to add the GET routes to.
        """
        # /api/

        class SolarModel(BaseModel):
            solar: float

        @app.get("/api/solar", response_model=SolarModel)
        async def get_solar() -> SolarModel:
            return SolarModel(solar=float(self._redis_get("solar")))

        class CiModel(BaseModel):
            ci: float

        @app.get("/api/ci", response_model=CiModel)
        async def get_ci() -> CiModel:
            return CiModel(ci=float(self._redis_get("ci")))

        class BatterySocModel(BaseModel):
            battery_soc: float

        @app.get("/api/battery-soc", response_model=BatterySocModel)
        async def get_battery_soc() -> BatterySocModel:
            return BatterySocModel(
                battery_soc=float(self._redis_get("battery_soc"))
            )

        # /sim/

        class CollectSetModel(BaseModel):
            battery_min_soc: float
            battery_grid_charge: float
            nodes_power_mode: dict[int, str]

        @app.get("/sim/collect-set", response_model=CollectSetModel)
        async def get_collect_set() -> CollectSetModel:
            return CollectSetModel(
                # good enough for now
                battery_min_soc=self.battery_min_soc_log[-1],
                battery_grid_charge=self.battery_grid_charge_log[-1],
                nodes_power_mode = {list(entry.keys())[0]: list(entry.values())[0]
                                    for entry in self.power_mode_log}
)

    def _init_put_routes(self, app: FastAPI) -> None:
        """Initialize PUT routes for the FastAPI application.

        Two PUT routes are set up: '/ves/battery' to update the battery
        settings, and '/cs/nodes/{item_id}' to update the power mode of a
        specific node. This method handles data validation and updates the
        corresponding attributes in the application instance and Redis
        datastore.

        Args:
            app: FastAPI application instance to which PUT routes are added.
        """
        # /api/

        self.battery_min_soc_log = []
        self.battery_grid_charge_log = []
        self.power_mode_log: list[dict[int, str]] = []

        class BatteryModel(BaseModel):
            min_soc: float
            grid_charge: float

        @app.put("/api/battery", response_model=BatteryModel)
        async def put_battery(battery: BatteryModel) -> BatteryModel:
            self.redis_docker.redis.set("battery_min_soc", battery.min_soc)
            self.battery_min_soc_log.append(battery.min_soc)
            self.redis_docker.redis.set("battery_grid_charge", battery.grid_charge)
            self.battery_grid_charge_log.append(battery.grid_charge)
            return battery

        class NodeModel(BaseModel):
            power_mode: str

        @app.put("/api/nodes/{item_id}", response_model=NodeModel)
        async def put_nodes(node: NodeModel, item_id: int) -> NodeModel:
            power_modes = ["power-saving", "normal", "high performance"]
            power_mode = node.power_mode
            if power_mode not in power_modes:
                raise HTTPException(
                    status_code=400,
                    detail=f"{power_mode} is not a valid power mode. "
                           f"Available power modes: {power_modes}"
            )
            self.power_mode_log.append({item_id: power_mode})
            self.redis_docker.redis.hset(
                "node_power_mode",
                str(item_id),
                power_mode
            )
            return node

        # /sim/

        class UpdateModel(BaseModel):
            solar: float
            ci: float
            battery_soc: float
            battery_min_soc: float
            battery_grid_charge: float
            nodes_power_mode: dict[int, str]

        @app.put("/sim/update", response_model=UpdateModel)
        async def put_update(update: UpdateModel) -> UpdateModel:
            self.redis_docker.redis.set("solar", update.solar)
            self.redis_docker.redis.set("battery_soc", update.battery_soc)
            self.redis_docker.redis.set("battery_min_soc", update.battery_min_soc)
            self.redis_docker.redis.set("battery_grid_charge", update.battery_grid_charge)
            for node_id, power_mode in update.nodes_power_mode.values():
                self.redis_docker.redis.hset("nodes_power_mode", str(node_id), power_mode)
            return update


    def _print_redis(self):
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

