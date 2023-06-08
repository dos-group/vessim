from abc import ABC, abstractmethod
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
import uvicorn

class PowerMode(BaseModel):
    power_mode: str

class FastApiServer(ABC):
    """An abstract base class that represents a FastAPI server.

    Args:
        host: The host on which to run the FastAPI application.
        port: The port on which to run the FastAPI application.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8000):
        self.app = FastAPI()
        self.host = host
        self.port = port
        self.power_mode = "high performance"
        self.setup_routes()

    def setup_routes(self) -> None:
        """Setup the routes for the FastAPI application. """
        @self.app.put("/power_mode")
        async def set_power_mode(power_mode: PowerMode) -> str:
            return self.set_power_mode(power_mode.power_mode)

        @self.app.get("/power_mode")
        async def get_power_mode() -> str:
            return self.power_mode

        @self.app.get("/power")
        async def get_power() -> float:
            return self.get_power()

    @abstractmethod
    def set_power_mode(self, power_mode: str) -> str:
        """Set the power mode for the server.

        Args:
            power_mode: The power mode to set.

        Returns:
            The new power mode.
        """
        power_modes = ["power-saving", "normal", "high performance"]
        if power_mode not in power_modes:
            raise HTTPException(
                status_code=400,
                detail=f"{power_mode} is not a valid power mode. "
                       f"Available power modes: {power_modes}"
            )
        self.power_mode = power_mode

    @abstractmethod
    def get_power(self) -> float:
        """Get the power usage.

        Returns:
            The current power usage.
        """
        pass

    def start(self):
        """Start the FastAPI application with a uvicorn server."""
        uvicorn.run(self.app, host=self.host, port=self.port)
