import time
from abc import ABC, abstractmethod
from threading import Thread

from vessim._util import HttpClient


class PowerMeter(ABC):

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def measure(self) -> float:
        """Abstract method to measure and return the current node power demand."""

    def finalize(self) -> None:
        """Perform necessary finalization tasks of a node."""


class MockPowerMeter(PowerMeter):

    def __init__(self, name: str, p: float):
        super().__init__(name)
        self._p = p

    def set_power(self, value):
        if value < 0:
            raise ValueError("p must not be less than 0")
        self._p = value

    def measure(self) -> float:
        return self._p


class HttpPowerMeter(PowerMeter):

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
        return self._p

    def _collect_loop(self) -> None:
        """Gets the power demand every `interval` seconds from the API server."""
        while True:
            self._p = float(self.http_client.get("/power")["power"])
            time.sleep(self.collect_interval)
