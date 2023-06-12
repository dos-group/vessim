from abc import ABC, abstractmethod
from typing import Optional
from lib.http_client import HTTPClient
import threading
import time


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

    This class represents a power meter for an external node. It creates a thread
    that updates the power demand from the node API at a given interval.

    Args:
        interval: The interval in seconds to update the power demand.
        server_address: The server address of the node API.
        port: The port number for the node API. Defaults to 8000.
        name: The name of the power meter. If None, a default name will be assigned. Defaults to None.

    Attributes:
        http_client: An instance of the HTTPClient pointed at the node API server.
        power: The current power demand of the node, updated every 'interval' seconds.
    """

    def __init__(
        self,
        interval: int,
        server_address: str,
        port: int = 8000,
        name: Optional[str] = None
    ) -> None:
        super().__init__(name)
        self.http_client = HTTPClient(f"{server_address}:{port}")
        self.power = 0
        self.update_thread = threading.Thread(target=self._update_power, args=(interval,))
        self.update_thread.daemon = True
        self.update_thread.start()

    def _update_power(self, interval: int) -> None:
        """Updates the power demand every 'interval' seconds by making a GET
        request to the node API."""
        while True:
            self.power = float(self.http_client.get("/power"))
            time.sleep(interval)

    def measure(self) -> float:
        """Returns the current power demand of the node."""
        return self.power

    def __del__(self) -> None:
        """Makes sure the thread that updates the power demand terminated when
        the instance is deleted."""
        if self.update_thread.is_alive():
            self.update_thread.join()


class MockPowerMeter(PowerMeter):

    def __init__(self, p: float, name: Optional[str] = None):
        super().__init__(name)
        assert p <= 0
        self.p = p

    def measure(self) -> float:
        return self.p
