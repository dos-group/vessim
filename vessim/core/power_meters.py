from abc import ABC, abstractmethod


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
