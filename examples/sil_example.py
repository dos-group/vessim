from __future__ import annotations

from threading import Thread
from fastapi import FastAPI
import time
import requests

from vessim.actor import ComputingSystem, Generator
from vessim.controller import Monitor
from vessim.cosim import Environment, Microgrid
from vessim.power_meter import PowerMeter
from vessim.signal import Signal, HistoricalSignal
from vessim.sil import SilController, Broker, get_latest_event
from vessim.storage import SimpleBattery


def main(result_csv: str):
    environment = Environment(sim_start="15-06-2022")

    monitor = Monitor()  # stores simulation result on each step
    sil_controller = SilController(  # executes software-in-the-loop controller
        api_routes=api_routes,
        request_collectors={"battery_min_soc": battery_min_soc_collector},
    )
    environment.add_microgrid(
        actors=[
            ComputingSystem(power_meters=HttpPowerMeter(name="sample_app", port=8001)),
            Generator(signal=HistoricalSignal.from_dataset("solcast2022_global"), column="Berlin"),
        ],
        storage=SimpleBattery(capacity=100),
        controllers=[monitor, sil_controller],
        step_size=60,  # global step size (can be overridden by actors or controllers)
    )

    environment.run(until=24 * 3600, rt_factor=1, print_progress=False)
    monitor.to_csv(result_csv)


def api_routes(
    app: FastAPI,
    broker: Broker,
    grid_signals: dict[str, Signal],
):
    @app.put("/battery/min-soc")
    async def put_battery_min_soc(min_soc: float):
        broker.set_event("battery_min_soc", min_soc)


# curl -X PUT http://localhost:8000/battery/min-soc \
#   -d '{"min_soc": 0.3}' \
#   -H 'Content-Type: application/json'
def battery_min_soc_collector(events: dict, microgrid: Microgrid, **kwargs):
    print(f"Received battery.min_soc events: {events}")
    microgrid.storage.min_soc = get_latest_event(events)


class HttpPowerMeter(PowerMeter):
    def __init__(
        self,
        name: str,
        port: int = 8000,
        address: str = "127.0.0.1",
        collect_interval: float = 1,
    ) -> None:
        super().__init__(name)
        self.port = port
        self.address = address
        self.collect_interval = collect_interval
        self._p = 0.0
        Thread(target=self._collect_loop, daemon=True).start()

    def measure(self) -> float:
        return self._p

    def _collect_loop(self) -> None:
        while True:
            self._p = float(
                requests.get(
                    f"{self.address}:{self.port}/power",
                ).text
            )
            time.sleep(self.collect_interval)


if __name__ == "__main__":
    main(result_csv="result.csv")
