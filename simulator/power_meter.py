from typing import Optional
from lib.http_client import HTTPClient

# Global variable to keep track of the count of power meters
POWER_METER_COUNT = 0

class PowerMeter():
    """Power meter.

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


    def power(self) -> float:
        """Measure and return the current node power demand."""
        return float(self.http_client.get("/power"))
