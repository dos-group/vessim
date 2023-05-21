from ..node_api_server import FastAPIServer
from lib.pi_monitor import PiMonitor

class rpi_api_server(FastAPIServer):
    def __init__(self, host: str = "localhost", port: int = 8000):
        super().__init__(host, port)
        self.pi_monitor = PiMonitor()


    def set_power_mode(self, power_mode: str) -> str:
        super().set_power_mode(power_mode)
        match power_mode:
            case "power-saving":
                self.pi_monitor.set_max_frequency(800 * 1000)
            case "normal":
                self.pi_monitor.set_max_frequency(1100 * 1000)
            case "high performance":
                self.pi_monitor.set_max_frequency(1400 * 1000)
        return power_mode


    def get_power(self) -> float:
        return self.pi_monitor.power()


if __name__ == "__main__":
    server = rpi_api_server()
