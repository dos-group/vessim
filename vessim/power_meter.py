from __future__ import annotations

from abc import ABC, abstractmethod
from itertools import count
from typing import Optional


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
