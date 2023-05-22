from abc import ABC, abstractmethod
from typing import Callable, Optional
from ..lib.http_client import HTTPClient

# Callable for power model
PowerModel = Callable[[float], float]

# Global variable to keep track of the count of power meters
POWER_METER_COUNT = 0

class LinearPowerModel:
    """Class for implementing a linear power model.

    Attributes:
        p_static: The static power component.
        p_max: The maximum power component.
    """

    def __init__(self, p_static, p_max):
        self.p_static = p_static
        self.p_max = p_max


    def __call__(self, utilization: float) -> float:
        """Compute power based on utilization.

        Args:
            utilization: A float representing current utilization.

        Returns:
            Power value as a float based on utilization.
        """
        return self.p_static + utilization * (self.p_max - self.p_static)


class PowerMeter(ABC):
    """Abstract base class for power meter.

    Attributes:
        server_address: Server address as a string.
        name: Name of the power meter as a string. Default to None.
    """

    def __init__(self, server_address: str, name: Optional[str] = None):
        self.http_client = HTTPClient(server_address)
        global POWER_METER_COUNT
        POWER_METER_COUNT += 1
        if name is None:
            self.name = f"power_meter_{POWER_METER_COUNT}"
        else:
            self.name = name


    @abstractmethod
    def node_power(self) -> float:
        """Abstract method to measure and return the current node power demand."""
        pass


class PhysicalPowerMeter(PowerMeter):
    """A class to represent a physical power meter. Inherits from PowerMeter class."""

    def node_power(self) -> float:
        """Overriding node_power method from PowerMeter.

        Returns:
            Current node power demand as a float.
        """
        return float(self.http_client.get("/power"))


class VirtualPowerMeter(PowerMeter):
    """A class to represent a virtual power meter. Inherits from PowerMeter class.

    Attributes:
        power_model: A callable power model.
    """

    def __init__(self, server_address: str, power_model: PowerModel, name: Optional[str] = None):
        super().__init__(server_address, name)
        self.power_model = power_model


    def node_power(self):
        """Overriding node_power method from PowerMeter.

        Returns:
            Current node power demand as a float based on utilization.
        """
        return self.power_model(self.utilization())


    def utilization(self) -> float:
        """Method to measure and return the current utilization.

        Returns:
            Current utilization as a float.
        """
        return float(self.http_client.get("/cpu"))
