from abc import ABC, abstractmethod
from typing import Optional
from lib.http_client import HTTPClient


class PowerMeter(ABC):
    """Abstract base class for power meters.

    Args:
        name: Optional; The name of the power meter.
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


class HttpPowerMeter(PowerMeter):
    """Power meter for an external node that implements the vessim node API.

    Args:
        server_address: The server address of the node API.
        port: The port number for the node API. Default is 8000.
        name: Optional; The name of the power meter. If none is provided, a
              default name will be assigned.

    Attributes:
        http_client: An instance of the HTTPClient pointed at the node API server.
    """

    def __init__(self, server_address: str, port: int = 8000, name: Optional[str] = None):
        super().__init__(name)
        self.http_client = HTTPClient(f"{server_address}:{port}")

    def measure(self) -> float:
        """Measure and return the current node power demand by making a GET
        request to the node API.

        Returns:
            float: The current power demand of the node.
        """
        return float(self.http_client.get("/power"))


class MockPowerMeter(PowerMeter):

    def __init__(self, return_value: float, name: Optional[str] = None):
        super().__init__(name)
        self.return_value = return_value

    def measure(self) -> float:
        return self.return_value
