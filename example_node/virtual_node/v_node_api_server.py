from ..node_api_server import FastAPIServer
from fastapi import HTTPException
import subprocess

class rpi_api_server(FastAPIServer):
    def __init__(self, host: str = "localhost", port: int = 8000):
        super().__init__(host, port)
        self.pid = None
        self.power_config = {
            "power-saving": 50,
            "normal": 70,
            "high performance": 100
        }


    def set_power_mode(self, power_mode: str) -> str:
        super().set_power_mode(power_mode)
        if self.pid is None:
            raise HTTPException(
                status_code=400,
                detail="Please first specify the PID of a process to limit its cpu usage."
            )
        self.cpulimit(self.pid, self.power_config[power_mode])
        return power_mode


    def get_power(self) -> float:
        raise HTTPException(
            status_code=405,
            detail="Virtual nodes can not measure their own power consumption."
        )


    def set_pid(self, pid: int) -> int:
        self.pid = pid
        self.cpulimit(pid, self.power_config[self.power_mode])
        return pid


    def cpulimit(self, pid: int, limit_percent: int) -> None:
        try:
            # find and kill any existing cpulimit processes targeting the same PID
            subprocess.run(
                ["pkill", "-f", f"cpulimit -p {pid}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            # start a new cpulimit process targeting the specified PID
            command = ["cpulimit", "-p", str(pid), "-l", str(limit_percent)]
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error occurred while executing cpulimit: {e}"
            )


if __name__ == "__main__":
    server = rpi_api_server()
