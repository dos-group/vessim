import sys
sys.path.append("../")
from node_api_server import FastApiServer
from lib.pi_controller import PiController
from fastapi import HTTPException

class RpiNodeApiServer(FastApiServer):
    """A Raspberry Pi node API server, extending the base FastApiServer class.

    Args:
        host: The host on which to run the FastAPI application.
        port: The port on which to run the FastAPI application.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8000):
        super().__init__(host, port)
        self.pi_controller = PiController()
        self.power_config = {
            "power-saving": 800 * 1000,
            "normal": 1100 * 1000,
            "high performance": 1400 * 1000,
        }
        self.start()

    def set_power_mode(self, power_mode: str) -> str:
        """Sets power mode for server and adjusts the max frequency of Pi accordingly.

        Args:
            power_mode: The power mode to set.

        Returns:
            The new power mode.
        """
        super().set_power_mode(power_mode)
        self.pi_controller.set_max_frequency(self.power_config[power_mode])
        return power_mode

    def get_power(self) -> float:
        """Get the power usage of the Raspberry Pi.

        Returns:
            The current power usage.
        """
        return self.pi_controller.power()


if __name__ == "__main__":
    server = RpiNodeApiServer()
