from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List

from vessim import TimeSeriesApi


class PowerMeter(ABC):
    """Abstract base class for power meters.

    Args:
        name: The name of the power meter.
    """

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def measure(self) -> float:
        """Abstract method to measure and return the current node power demand.

        Returns:
            float: The current power demand of the node.
        """

    @abstractmethod
    def finalize(self) -> None:
        """Perform necessary finalization tasks of specific power meter."""


class MockPowerMeter(PowerMeter):
    """Simulates the behavior of a power meter with fixed power readings.

    Args:
        name: The name of the power meter.
        p: Base factor for the measured power value. It is scaled by the consumption
            factors in the different power modes specified in the power config.

    Attributes:
        factor: Scaling factor, multiplied with the base factor. Defaults to 1.

    Raises:
        ValueError: If p is less than 0.
    """

    def __init__(self, name: str, p: float):
        super().__init__(name)
        if p < 0:
            raise ValueError("p must not be less than 0")
        self.p = p
        self.factor = 1.0

    def measure(self) -> float:
        return self.p * self.factor

    def finalize(self) -> None:
        pass


class Actor(ABC):
    """Abstract base class representing a power consumer or producer."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def p(self, now: datetime) -> float:
        """Return the power consumption/production of the actor."""

    def info(self, now: datetime) -> Dict:
        """Return additional information about the state of the actor."""
        return {}

    def finalize(self) -> None:
        """Perform any finalization tasks for the consumer.

        This method can be overridden by subclasses to implement necessary
        finalization steps.
        """
        return


class ComputingSystem(Actor):
    """Model of the computing system.

    This model considers the power usage effectiveness (PUE) and power
    consumption of a list of power meters.

    Args:
        power_meters: A list of PowerMeter objects
            representing power meters in the system.
        pue: The power usage effectiveness of the system.
    """

    def __init__(self, name: str, power_meters: List[PowerMeter], pue: float = 1):
        super().__init__(name)
        self.power_meters = power_meters
        self.pue = pue

    def p(self, now: datetime) -> float:
        return self.pue * sum(-pm.measure() for pm in self.power_meters)

    def info(self, now: datetime) -> Dict:
        return {pm.name: -pm.measure() for pm in self.power_meters}

    def finalize(self) -> None:
        for power_meter in self.power_meters:
            power_meter.finalize()


class Generator(Actor):

    def __init__(self, name: str, time_series_api: TimeSeriesApi):
        super().__init__(name)
        self.time_series_api = time_series_api

    def p(self, now: datetime) -> float:
        return self.time_series_api.actual(now)  # TODO TimeSeriesApi must be for a single region
