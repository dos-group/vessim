from abc import ABC, abstractmethod
from fastapi import FastAPI, HTTPException
import psutil

class FastAPIServer(ABC):
    def __init__(self, host: str = "localhost", port: int = 8000):
        self.app = FastAPI()
        self.host = host
        self.port = port

        self.power_mode = "high-performance"

        self.setup_routes()
        self.start()


    def setup_routes(self) -> None:
        @self.app.put("/power_mode")
        async def set_power_mode(power_mode: str) -> str:
            return self.set_power_mode(power_mode)
        @self.app.get("/power_mode")
        async def get_power_mode() -> str:
            return self.power_mode
        @self.app.get("/cpu")
        async def get_cpu() -> float:
            return psutil.cpu_percent(1)
        @self.app.get("/power")
        async def get_power() -> float:
            return self.get_power()
        @self.app.get("/pid")
        async def set_pid(pid: int) -> int:
            return self.set_pid(pid)


    @abstractmethod
    def set_power_mode(self, power_mode: str) -> str:
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
        pass


    @abstractmethod
    def set_pid(self, pid: int) -> int:
        pass


    def start(self):
        self.app.run(host=self.host, port=self.port)
