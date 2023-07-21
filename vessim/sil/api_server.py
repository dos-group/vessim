import multiprocessing
from time import sleep
from datetime import datetime
from typing import Optional, Dict

import uvicorn  # type: ignore
from fastapi import FastAPI, HTTPException  # type: ignore
from pydantic import BaseModel  # type: ignore


class ApiServer(multiprocessing.Process):
    """Process that runs a given FastAPI application with a uvicorn server.

    Args:
        app: FastAPI, the FastAPI application to run
        host: The host address, defaults to '127.0.0.1'.
        port: The port to run the FastAPI application, defaults to 8000.
    """

    def __init__(self, app: FastAPI, host: str = "127.0.0.1", port: int = 8000) -> None:
        super().__init__()
        self.host = host
        self.port = port
        self.app = app
        self.startup_complete = multiprocessing.Value('b', False)

        @self.app.on_event("startup")
        async def startup_event():
            self.startup_complete.value = True

    def wait_for_startup_complete(self):
        """Waiting for completion of startup process.

        To ensure the server is operational for the simulation, the startup
        needs to complete before any requests can be made. Waits for the
        uvicorn server to finish startup.
        """
        while not self.startup_complete.value:
            sleep(1)

    def run(self):
        """Called with `multiprocessing.Process.start()`. Runs the uvicorn server."""
        config = uvicorn.Config(
            app=self.app, 
            host=self.host, 
            port=self.port, 
            access_log=False
        )
        server = uvicorn.Server(config=config)
        server.run()


class VessimApiServer(ApiServer):
    """Specialized ApiServer class for the Vessim API.

    Inherits from ApiServer class and extends it by adding specific attributes
    related to Vessim API and methods to initialize FastAPI application with
    specific routes.

    Args:
        host: The host address.
        port: The port to run the FastAPI application.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8000) -> None:
        self.solar: Optional[float] = None
        self.ci: Optional[float] = None
        self.battery_soc: Optional[float] = None

        self.battery_min_soc_log: Dict[str, float] = {}
        self.battery_grid_charge_log: Dict[str, float] = {}
        self.power_mode_log: Dict[str, Dict[int, str]] = {}

        app = self._init_fastapi()
        super().__init__(app, host, port)

    def _init_fastapi(self) -> FastAPI:
        """Initializes the FastAPI application.

        Returns:
            FastAPI: The initialized FastAPI application.
        """
        app = FastAPI()
        self._init_get_routes(app)
        self._init_put_routes(app)
        return app

    def _init_get_routes(self, app: FastAPI) -> None:
        """Initializes GET routes for a FastAPI.

        Args:
            app: The FastAPI app to add the GET routes to.
        """
        # /api/

        class SolarModel(BaseModel):
            solar: Optional[float]

        @app.get("/api/solar", response_model=SolarModel)
        async def get_solar() -> SolarModel:
            return SolarModel(solar=self.solar)

        class CiModel(BaseModel):
            ci: Optional[float]

        @app.get("/api/ci", response_model=CiModel)
        async def get_ci() -> CiModel:
            return CiModel(ci=self.ci)

        class BatterySocModel(BaseModel):
            battery_soc: Optional[float]

        @app.get("/api/battery-soc", response_model=BatterySocModel)
        async def get_battery_soc() -> BatterySocModel:
            return BatterySocModel(battery_soc=self.battery_soc)

        # /sim/

        class CollectSetModel(BaseModel):
            battery_min_soc: Optional[Dict[str, float]]
            battery_grid_charge: Optional[Dict[str, float]]
            nodes_power_mode: Optional[Dict[str, Dict[int, str]]]

        @app.get("/sim/collect-set", response_model=CollectSetModel)
        async def get_collect_set() -> CollectSetModel:
            model = CollectSetModel(
                battery_min_soc=self.battery_min_soc_log,
                battery_grid_charge=self.battery_grid_charge_log,
                nodes_power_mode=self.power_mode_log
            )
            self.battery_min_soc_log.clear()
            self.battery_grid_charge_log.clear()
            self.power_mode_log.clear()
            return model

    def _init_put_routes(self, app: FastAPI) -> None:
        """Initialize PUT routes for the FastAPI application.

        Args:
            app: FastAPI application instance to which PUT routes are added.
        """
        # /api/

        class BatteryModel(BaseModel):
            min_soc: float
            grid_charge: float

        @app.put("/api/battery", response_model=BatteryModel)
        async def put_battery(battery: BatteryModel) -> BatteryModel:
            timestamp = datetime.now().isoformat()
            self.battery_min_soc_log[timestamp] = battery.min_soc
            self.battery_grid_charge_log[timestamp] = battery.grid_charge
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
            timestamp = datetime.now().isoformat()
            self.power_mode_log[timestamp] = {item_id: power_mode}
            return node

        # /sim/

        class UpdateModel(BaseModel):
            solar: float
            ci: float
            battery_soc: float

        @app.put("/sim/update", response_model=UpdateModel)
        async def put_update(update: UpdateModel) -> UpdateModel:
            self.solar = update.solar
            self.ci = update.ci
            self.battery_soc = update.battery_soc
            return update

