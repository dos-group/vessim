from __future__ import annotations

import time
from abc import ABC, abstractmethod
from itertools import count
from threading import Thread
from typing import Optional

try:
    from vessim.sil import HttpClient

    _has_sil = True
except ImportError:
    _has_sil = False


class PowerMeter(ABC):
    _ids = count(0)

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def measure(self) -> float:
        """Abstract method to measure and return the current node power demand."""

    def finalize(self) -> None:
        """Perform necessary finalization tasks of a node."""


class MockPowerMeter(PowerMeter):
    def __init__(self, p: float, name: Optional[str] = None):
        if name is None:
            name = f"MockPowerMeter-{next(self._ids)}"
        super().__init__(name)
        if p < 0:
            raise ValueError("p must not be less than 0")
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
        if not _has_sil:
            raise RuntimeError("Install the vessim[sil] extension to use this class.")
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
