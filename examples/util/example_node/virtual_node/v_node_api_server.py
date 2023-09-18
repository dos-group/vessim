import sys
from typing import Union
sys.path.append("../")
from linear_power_model import LinearPowerModel
from node_api_server import FastApiServer
import subprocess
import multiprocessing
import psutil
import re

class VirtualNodeApiServer(FastApiServer):
    """This class is a virtual node API server, extending FastApiServer.

    The server continuosely runs a sysbench instance that puts load on the CPU.
    Depending on the `power_mode`, the sysbench instance claims different CPU
    utilisation.

    Args:
        host: The host on which to run the FastAPI application.
        port: The port on which to run the FastAPI application.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8000):
        super().__init__(host, port)
        self.power_model = LinearPowerModel(p_static=4.8, p_max=8.8)
        self.power_config = None
        self.sysbench = None
        self._run_benchmark()
        self._restart_sysbench(run_forever=True)
        self.start()

    def set_power_mode(self, power_mode: str) -> None:
        """Set the power mode for the server.

        Args:
            power_mode: The desired power mode. Can be "high performance",
                "normal" or "power-saving".
        """
        super().set_power_mode(power_mode)
        self._restart_sysbench(run_forever=True)

    def get_power(self) -> float:
        """Get the power usage of the virtual node.

        Returns:
            The current power usage.
        """
        return self.power_model(psutil.cpu_percent(1) / 100)

    def _restart_sysbench(self, run_forever: bool = False) -> None:
        """Kill the existing sysbench instance and start a new one.

        Args:
            run_forever: Whether the sysbench should run indefinitely (1 year).
                Defaults to False.
        """
        # Kill the potentially running sysbench instance
        if self.sysbench:
            self.sysbench.kill()
            self.sysbench = None

        # Define the command and arguments
        max_threads = multiprocessing.cpu_count()
        command = ["sysbench", "cpu", "run", f"--threads={max_threads}"]
        if self.power_config:
            power_mode = (self.power_mode if self.power_mode
                         else list(self.power_config.keys())[0])
            command.append(f"--rate={self.power_config[power_mode]}")
        if run_forever:
            # 1 year
            command.append("--time=31622400")

        # Start the new sysbench process
        self.sysbench = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) # type: ignore

    def _run_benchmark(self) -> None:
        """Run a sysbench benchmark.

        Obtain the cpu metric "events/s" in high performance mode to scale the
        target rate of the other power modes and achieve approximately linear
        CPU utilisation and save in `self.power_config`.

        """
        self._restart_sysbench()
        assert self.sysbench is not None

        # Wait till benchmark finishes and get output
        stdout, _ = self.sysbench.communicate()
        self.sysbench = None
        # Extract the events per second from the output
        pattern = r"events per second:\s+([\d.]+)"
        match = re.search(pattern, stdout)
        assert match is not None
        max_rate = float(match.group(1))

        self.power_config = {
            "high performance": int(max_rate),
            "normal": int(max_rate * .7),
            "power-saving": int(max_rate * .5)
        }


if __name__ == "__main__":
    server = VirtualNodeApiServer()
