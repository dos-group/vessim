"""Co-simulation example with software-in-the-loop.

This scenario builds on `controller_example.py` but connects to a real computing system
through software-in-the-loop integration as described in our paper:
- 'Software-in-the-loop simulation for developing and testing carbon-aware applications'.
  [under review]

This is example experimental and documentation is still in progress.
"""
from datetime import datetime
from typing import Optional, Dict

import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel

from _data import load_carbon_data, load_solar_data
from controller_example import (
    SIM_START,
    STORAGE,
    DURATION, POLICY
)
from vessim import TimeSeriesApi
from vessim.core.enviroment import Environment
from vessim.core.microgrid import Microgrid
from vessim.core.power_meter import HttpPowerMeter
from vessim.cosim.actor import ComputingSystem, Generator
from vessim.cosim.controller import Monitor
from vessim.sil import SilController, ComputeNode, Broker
from vessim.util import get_latest_event

RT_FACTOR = 1  # 1 wall-clock second ^= 60 sim seconds
GCP_ADDRESS = "http://35.198.148.144"
RASPI_ADDRESS = "http://192.168.207.71"


def main(result_csv: str):
    environment = Environment(sim_start=SIM_START)
    environment.add_grid_signal("carbon_intensity", TimeSeriesApi(load_carbon_data()))

    power_meters = [
        HttpPowerMeter(name="gcp", address=GCP_ADDRESS),
        HttpPowerMeter(name="raspi", address=RASPI_ADDRESS)
    ]
    monitor = Monitor(step_size=60)
    carbon_aware_controller = SilController(
        step_size=60,
        api_routes=api_routes,
        request_collectors={
            "battery_min_soc": battery_min_soc_collector,
            "battery_grid_charge": grid_charge_collector,
            "nodes_power_mode": node_power_mode_collector,
        },
        compute_nodes=[
            ComputeNode(name="gcp", address=GCP_ADDRESS),
            ComputeNode(name="raspi", address=RASPI_ADDRESS),
        ],
    )
    microgrid = Microgrid(
        actors=[
            ComputingSystem(
                name="server",
                step_size=60,
                power_meters=power_meters
            ),
            Generator(
                name="solar",
                step_size=60,
                time_series_api=TimeSeriesApi(load_solar_data(sqm=0.4 * 0.5))
            ),
        ],
        storage=STORAGE,
        storage_policy=POLICY,
        controllers=[monitor, carbon_aware_controller],  # first executes monitor, then controller
        zone="DE",
    )

    environment.add_microgrid(microgrid)
    environment.run(until=DURATION, rt_factor=RT_FACTOR, print_progress=False)
    monitor.monitor_log_to_csv(result_csv)


def api_routes(
    app: FastAPI,
    broker: Broker,
    grid_signals: Dict[str, TimeSeriesApi],
):
    @app.get("/actors/{actor}/p")
    async def get_solar(actor: str):
        return broker.get_actor(actor)["p"]

    @app.get("/battery/soc")
    async def get_battery_soc():
        return broker.get_microgrid().storage.soc()

    @app.get("/grid-power")
    async def get_grid_energy():
        return broker.get_grid_power()

    @app.get("/carbon-intensity")
    async def get_carbon_intensity(time: Optional[str]):
        time = pd.to_datetime(time) if time is not None else datetime.now()
        return grid_signals["carbon_intensity"].actual(time)

    class BatteryModel(BaseModel):
        min_soc: Optional[float]
        grid_charge: Optional[float]

    @app.put("/battery")
    async def put_battery(battery_model: BatteryModel):
        broker.set_event("battery_min_soc", battery_model.min_soc)
        broker.set_event("battery_grid_charge", battery_model.grid_charge)

    class NodeModel(BaseModel):
        power_mode: str

    @app.put("/nodes/{node_name}")
    async def put_nodes(node: NodeModel, node_name: str):
        broker.set_event("nodes_power_mode", {node_name: node.power_mode})


# curl -X PUT -d '{"min_soc": 0.5,"grid_charge": 1}' http://localhost:8000/battery -H 'Content-Type: application/json'
def battery_min_soc_collector(events: Dict, microgrid: Microgrid, compute_nodes: Dict):
    print(f"Received battery.min_soc events: {events}")
    microgrid.storage.min_soc = get_latest_event(events)


def grid_charge_collector(events: Dict, microgrid: Microgrid, compute_nodes: Dict):
    print(f"Received grid_charge events: {events}")
    microgrid.storage_policy.grid_power = get_latest_event(events)


# curl -X PUT -d '{"power_mode": "normal"}' http://localhost:8000/nodes/gcp -H 'Content-Type: application/json'
def node_power_mode_collector(events: Dict, microgrid: Microgrid, compute_nodes: Dict):
    print(f"Received nodes_power_mode events: {events}")
    latest = get_latest_event(events)
    for node_name, power_mode in latest.items():
        compute_node: ComputeNode = compute_nodes[node_name]
        compute_node.set_power_mode(power_mode)


if __name__ == "__main__":
    main(result_csv="result.csv")
