from fastapi import FastAPI
from threading import Thread
import math
import random
import time
import uvicorn


class NodeApiServer:
    def __init__(self, port: int, p_static: float, p_max: float):
        self.app = FastAPI()
        self.port = port
        self.p_static = p_static
        self.p_max = p_max
        Thread(target=self._workload_sim, daemon=True).start()

        @self.app.get("/power")
        async def get_power():
            return self.p_static + self.utilization * (self.p_max - self.p_static)

    def _workload_sim(self):
        while True:
            end = time.time() + 10
            while time.time() < end:
                self.utilization = random
            self.utilization = 0.05
            time.sleep(10)

    def start(self):
        uvicorn.run(self.app, host="0.0.0.0", port=self.port)


if __name__ == "__main__":
    NodeApiServer(port=8001, p_static=4, p_max=8).start()
