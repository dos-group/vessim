from vessim.core import VessimSimulator, VessimModel
from typing import List
from abc import ABC, abstractmethod
from typing import Optional
from lib.http_client import HTTPClient
import threading
import time


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


class HttpPowerMeter(PowerMeter):
    """Power meter for an external node that implements the vessim node API.

    This class represents a power meter for an external node. It creates a thread
    that updates the power demand from the node API at a given interval.

    Args:
        interval: The interval in seconds to update the power demand.
        server_address: The IP address of the node API.
        port: The IP port of the node API.
        name: The name of the power meter.
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
        """Gets the power demand every `interval` seconds from the API server."""
        while True:
            self.power = float(self.http_client.get("/power"))
            time.sleep(interval)

    def measure(self) -> float:
        """Returns the current power demand of the node."""
        return self.power

    def __del__(self) -> None:
        """Terminates the power demand update thread when the instance is deleted."""
        if self.update_thread.is_alive():
            self.update_thread.join()


class MockPowerMeter(PowerMeter):

    def __init__(self, p: float, name: Optional[str] = None):
        super().__init__(name)
        assert p <= 0
        self.p = p

    def measure(self) -> float:
        return self.p


class ComputingSystemSim(VessimSimulator):
    """Computing System simulator that executes its model."""

    META = {
        "type": "time-based",
        "models": {
            "ComputingSystem": {
                "public": True,
                "params": ["power_meters", "pue"],
                "attrs": ["p"],
            },
        },
    }

    def __init__(self):
        self.step_size = None
        super().__init__(self.META, ComputingSystemModel)

    def init(self, sid, time_resolution, step_size, eid_prefix=None):
        self.step_size = step_size
        return super().init(sid, time_resolution, eid_prefix=eid_prefix)

    def next_step(self, time):
        return time + self.step_size


class ComputingSystemModel(VessimModel):
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
        self.p = 0.0

    def step(self, time: int, inputs: dict) -> None:
        """Updates the power consumption of the system.

        The power consumption is calculated as the product of the PUE and the
        sum of the node power of all power meters.
        """
        self.p = self.pue * sum(pm.measure() for pm in self.power_meters)
