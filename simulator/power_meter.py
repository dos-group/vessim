from abc import ABC, abstractmethod
from typing import Optional
from lib.http_client import HTTPClient

POWER_METER_COUNT = 0

class PowerMeter(ABC):
    """Abstract base class for power meters.

    Args:
        name: Optional; The name of the power meter.
              If none is provided, a default name will be assigned.

    Attributes:
        name: Optional; The name of the power meter.
              If none is provided, a default name will be assigned.

    Methods:
        __call__: Abstract method to measure and return the current node power demand.
    """

    def __init__(self, name: Optional[str] = None):
        global POWER_METER_COUNT
        POWER_METER_COUNT += 1
        if name is None:
            self.name = f"power_meter_{POWER_METER_COUNT}"
        else:
            self.name = name

    @abstractmethod
    def __call__(self) -> float:
        """Abstract method to measure and return the current node power demand.

        Returns:
            float: The current power demand of the node.
        """
        pass


class NodeApiMeter(PowerMeter):
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

    def __call__(self) -> float:
        """Measure and return the current node power demand by making a GET
        request to the node API.

        Returns:
            float: The current power demand of the node.
        """
        return float(self.http_client.get("/power"))

