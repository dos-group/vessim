import sys
sys.path.append("../")
from linear_power_model import LinearPowerModel
from node_api_server import FastApiServer
from fastapi import HTTPException
import subprocess
import psutil

class VirtualNodeApiServer(FastApiServer):
    """This class represents a virtual node API server, extending the base
    FastApiServer class.

    Args:
        host: The host on which to run the FastAPI application.
        port: The port on which to run the FastAPI application.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8000):
        self.pid = None
        self.power_config = {
            "power-saving": 50,
            "normal": 70,
            "high performance": 100
        }
        self.power_model = LinearPowerModel(p_static=30, p_max=150)
        super().__init__(host, port)


    def set_power_mode(self, power_mode: str) -> str:
        """Set the power mode for the server and limits the cpu usage of the
        process with the given PID.

        Args:
            power_mode: The power mode to set.

        Returns:
            The new power mode.

        Raises:
            HTTPException: If no PID is set before calling this method.
        """
        super().set_power_mode(power_mode)
        if self.pid is None:
            raise HTTPException(
                status_code=400,
                detail="Please first specify the PID of a process to limit its cpu usage."
            )
        self.cpulimit(self.pid, self.power_config[power_mode])
        return power_mode


    def get_power(self) -> float:
        """Get the power usage of the virtual node.

        Returns:
            The current power usage.
        """
        return self.power_model(psutil.cpu_percent(1))


    def set_pid(self, pid: int) -> int:
        """Set the PID for the server and limit its cpu usage according to the
        current power mode.

        Args:
            pid: The PID to set.

        Returns:
            The new PID.
        """
        self.pid = pid
        self.cpulimit(pid, self.power_config[self.power_mode])
        return pid


    def cpulimit(self, pid: int, limit_percent: int) -> None:
        """Limits the cpu usage of the process with the given PID.

        Args:
            pid: The PID of the process to limit.
            limit_percent: The percentage to which to limit the cpu usage.

        Raises:
            HTTPException: If an error occurs while executing the cpulimit command.
        """
        try:
            # find and kill any existing cpulimit processes targeting the same PID
            subprocess.run(
                ["pkill", "-f", f"cpulimit -p {pid}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            # start a new cpulimit process targeting the specified PID
            command = ["cpulimit", "-p", str(pid), "-l", str(limit_percent)]
            subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except subprocess.CalledProcessError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error occurred while executing cpulimit: {e}"
            )


if __name__ == "__main__":
    server = VirtualNodeApiServer()
