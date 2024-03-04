from __future__ import annotations

from datetime import datetime
import time
from typing import Optional
from threading import Thread

import pandas as pd
from fastapi import FastAPI

from vessim.actor import ComputingSystem, Generator
from vessim.controller import Monitor
from vessim.cosim import Environment, Microgrid
from vessim.power_meter import PowerMeter
from vessim.signal import Signal, HistoricalSignal
from vessim.sil import SilController, Broker, get_latest_event, HttpClient
from vessim.storage import SimpleBattery


def main(result_csv: str):
    environment = Environment(sim_start="15-06-2022")

    nodes = [
        ComputeNode(name="sample_app", port=8001),
    ]
    monitor = Monitor()  # stores simulation result on each step
    carbon_aware_controller = SilController(  # executes software-in-the-loop controller
        api_routes=api_routes,
        request_collectors={
            "nodes_power_mode": node_power_mode_collector,
        },
        kwargs={"compute_nodes": {node.name: node for node in nodes}},
    )
    environment.add_microgrid(
        actors=[
            ComputingSystem(power_meters=nodes),
            Generator(signal=HistoricalSignal.from_dataset("solcast2022_global"), column="Berlin"),
        ],
        storage=SimpleBattery(capacity=100),
        controllers=[monitor, carbon_aware_controller],
        step_size=60,  # global step size (can be overridden by actors or controllers)
    )

    environment.run(until=24 * 3600, rt_factor=1, print_progress=False)
    monitor.to_csv(result_csv)


def api_routes(
    app: FastAPI,
    broker: Broker,
    grid_signals: dict[str, Signal],
):
    @app.get("/actors/{actor}/p")
    async def get_actor(actor: str):
        return broker.get_actor(actor)["p"]

    @app.get("/battery/soc")
    async def get_battery_soc():
        storage = broker.get_microgrid().storage
        assert storage is not None
        return storage.soc()

    @app.get("/carbon-intensity")
    async def get_carbon_intensity(time: Optional[str]):
        datetime_time = pd.to_datetime(time) if time is not None else datetime.now()
        return grid_signals["carbon_intensity"].at(datetime_time)

    @app.put("/nodes/{node_name}")
    async def put_nodes(node_name: str, power_mode: str):
        broker.set_event("nodes_power_mode", {node_name: power_mode})


# curl -X PUT -d '{"power_mode": "normal"}' http://localhost:8000/nodes/gcp -H 'Content-Type: application/json'
def node_power_mode_collector(events: dict, microgrid: Microgrid, **kwargs):
    print(f"Received nodes_power_mode events: {events}")
    latest = get_latest_event(events)
    for node_name, power_mode in latest.items():
        node: ComputeNode = kwargs["compute_nodes"][node_name]
        node.set_power_mode(power_mode)


class ComputeNode(PowerMeter):
    def __init__(
        self,
        name: str,
        port: int = 8000,
        address: str = "127.0.0.1",
        collect_interval: float = 1,
    ) -> None:
        super().__init__(name)
        self.http_client = HttpClient(f"{address}:{port}")
        self.collect_interval = collect_interval
        self.power_mode = self.power_modes()[0]
        self._p = 0.0
        Thread(target=self._collect_loop, daemon=True).start()

    def measure(self) -> float:
        return self._p

    def power_modes(self) -> list[str]:
        return ["high performance", "normal", "power-saving"]

    def set_power_mode(self, power_mode: str) -> None:
        if power_mode not in self.power_modes():
            raise ValueError(
                f"'{power_mode}' is not recognized. Available power modes are "
                f"{self.power_modes()}"
            )
        if power_mode == self.power_mode:
            return

        def update_power_model():
            self.http_client.put("/power_mode", {"power_mode": power_mode})

        Thread(target=update_power_model).start()
        self.power_mode = power_mode

    def _collect_loop(self) -> None:
        """Gets the power demand every `interval` seconds from the API server."""
        while True:
            self._p = float(self.http_client.get("/power")["power"])
            time.sleep(self.collect_interval)


if __name__ == "__main__":
    main(result_csv="result.csv")
