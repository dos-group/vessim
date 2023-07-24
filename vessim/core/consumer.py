from abc import ABC, abstractmethod
from typing import List, Optional


class PowerMeter(ABC):
    """Abstract base class for power meters.

    Args:
        name: The name of the power meter.
    """

    def __init__(self, name: Optional[str] = None):
        self.name = name

    @abstractmethod
    def measure(self) -> float:
        """Abstract method to measure and return the current node power demand.

        Returns:
            float: The current power demand of the node.
        """
        pass

    @abstractmethod
    def finalize(self) -> None:
        pass


class MockPowerMeter(PowerMeter):

    def __init__(self, p: float, name: Optional[str] = None):
        super().__init__(name)
        assert p >= 0
        self.p = p

    def measure(self) -> float:
        return self.p

    def finalize(self) -> None:
        pass


class Consumer(ABC):

    @abstractmethod
    def consumption(self) -> float:
        pass

    def finalize(self) -> None:
        pass


class ComputingSystem(Consumer):
    """Model of the computing system.

    This model considers the power usage effectiveness (PUE) and power
    consumption of a list of power meters.

    Args:
        power_meters: A list of PowerMeter objects
            representing power meters in the system.
        pue: The power usage effectiveness of the system.
    """

    def __init__(self, power_meters: List[PowerMeter], pue: float = 1):
        self.power_meters = power_meters
        self.pue = pue

    def consumption(self) -> float:
        return self.pue * sum(pm.measure() for pm in self.power_meters)

    def finalize(self) -> None:
        for power_meter in self.power_meters:
            power_meter.finalize()
