from ..node_api_server import FastAPIServer
from lib.pi_monitor import PiMonitor
from fastapi import HTTPException

class rpi_api_server(FastAPIServer):
    def __init__(self, host: str = "localhost", port: int = 8000):
        super().__init__(host, port)
        self.pi_monitor = PiMonitor()
        self.power_config = {
            "power-saving": 800 * 1000,
            "normal": 1100 * 1000,
            "high performance": 1400 * 1000
        }


    def set_power_mode(self, power_mode: str) -> str:
        super().set_power_mode(power_mode)
        self.pi_monitor.set_max_frequency(self.power_config[power_mode])
        return power_mode


    def get_power(self) -> float:
        return self.pi_monitor.power()


    def set_pid(self, pid: int) -> int:
        raise HTTPException(
            status_code=405,
            detail="The Raspberry Pi node uses DVFS instead of cpulimit "
                   "and requires no pid."
        )


if __name__ == "__main__":
    server = rpi_api_server()
