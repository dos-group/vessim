"""Co-simulation example with software-in-the-loop.

This scenario builds on `controller_example.py` but connects to a real computing system
through software-in-the-loop integration as described in our paper:
- 'Software-in-the-loop simulation for developing and testing carbon-aware applications'.
  [under review]

This is example experimental and documentation is still in progress.
"""
import json
import pickle
from datetime import datetime
from typing import Optional, Dict, Any

import pandas as pd
import redis
from fastapi import FastAPI, HTTPException
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
from vessim.cosim.actor import ComputingSystem, Generator
from vessim.cosim.controller import Monitor
from vessim.cosim.util import disable_mosaik_warnings
from vessim.sil.sil import SilController, latest_event

RT_FACTOR = 1  # 1 wall-clock second ^= 60 sim seconds
GCP_ADDRESS = "http://35.198.148.144"
RASPI_ADDRESS = "http://192.168.207.71"
disable_mosaik_warnings(behind_threshold=0.01)


def main(result_csv: str):
    environment = Environment(sim_start=SIM_START)
    environment.add_grid_signal("carbon_intensity", TimeSeriesApi(load_carbon_data()))

    # Initialize nodes
    nodes = [
        #Node(address=GCP_ADDRESS, id="gcp"),
        #Node(address=RASPI_ADDRESS, id="raspi")
    ]
    power_meters = [
        #HttpPowerMeter(name="mpm0", interval=1, server_address=GCP_ADDRESS),
        #HttpPowerMeter(name="mpm1", interval=1, server_address=RASPI_ADDRESS),
    ]
    monitor = Monitor(step_size=60)

    carbon_aware_controller = SilController(
        step_size=60,
        api_routes=api_routes,
        request_collectors={
            "battery_min_soc": battery_min_soc_collector,
            "battery_grid_charge": grid_charge_collector,
            "nodes_power_mode": nodes_power_mode_collector,
        },
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
    # TODO the following two arguments should be coupled into a
    #  class with helper functions for accessing Redis
    grid_signals: Dict[str, TimeSeriesApi],
    redis_db: redis.Redis
):
    @app.get("/")
    async def root():
        return "Hello World"

    @app.get("/carbon-intensity")
    async def get_carbon_intensity(time: Optional[str]):
        time = pd.to_datetime(time) if time is not None else datetime.now()
        return grid_signals["carbon_intensity"].actual(time)

    @app.get("/solar")
    async def get_solar():
        return json.loads(redis_db.get("actors"))["solar"]["p"]

    @app.get("/battery/soc")
    async def get_battery_soc():
        microgrid = pickle.loads(redis_db.get("microgrid"))
        return microgrid.storage.soc()

    @app.get("/grid-energy")
    async def get_grid_energy():
        return float(redis_db.get("p_delta"))

    class BatteryModel(BaseModel):
        min_soc: Optional[float]
        grid_charge: Optional[float]

    @app.put("/battery")
    async def put_battery(battery_model: BatteryModel):
        pipe = redis_db.pipeline()
        if battery_model.min_soc is not None:
            pipe.lpush("set_events", pickle.dumps({
                "key": "battery_min_soc",
                datetime.now().isoformat(): battery_model.min_soc,
            }))
        if battery_model.grid_charge is not None:
            redis_db.lpush("set_events", pickle.dumps({
                "key": "battery_grid_charge",
                datetime.now().isoformat(): battery_model.grid_charge,
            }))
        pipe.execute()

    class NodeModel(BaseModel):
        power_mode: str

    @app.put("/api/nodes/{item_id}")
    async def put_nodes(node: NodeModel, item_id: str) -> NodeModel:
        # TODO generalize
        power_modes = ["power-saving", "normal", "high performance"]
        power_mode = node.power_mode
        if power_mode not in power_modes:
            raise HTTPException(
                status_code=400,
                detail=f"{power_mode} is not a valid power mode. "
                f"Available power modes: {power_modes}",
            )
        redis_db.lpush("set_events", pickle.dumps({
            "key": "battery_grid_charge",
            datetime.now().isoformat(): {item_id: power_mode},
        }))


def battery_min_soc_collector(events: Dict[datetime, Any], microgrid: Microgrid):
    print(f"Received battery.min_soc events: {events}")
    microgrid.storage.min_soc = latest_event(events)


def grid_charge_collector(events: Dict[datetime, Any], microgrid: Microgrid):
    print(f"Received grid_charge events: {events}")
    microgrid.storage_policy.grid_power = latest_event(events)


def nodes_power_mode_collector(events: Dict[datetime, Any], microgrid: Microgrid):
    print(f"Received nodes_power_mode events: {events}")
    latest = latest_event(events)

    # TODO
    # nodes_power_mode looks e.g. like {"gcp": "normal",...}
    # Loop through all nodes,
    # for node in self.nodes:
    #     if node.id in nodes_power_mode:
    #         # update the power_mode if it changed
    #         node.power_mode = nodes_power_mode[node.id]
    #         # and save whatever node had its powermode updated to
    #         # remotely update only that nodes' power mode in step().
    #         self.updated_nodes.append(node)
    #
    # # update power mode for the node remotely
    # for node in self.updated_nodes:
    #     http_client = HttpClient(f"{node.address}:{node.port}")
    #
    #     def update_node_power_model():
    #         http_client.put("/power_mode", {"power_mode": node.power_mode})
    #
    #     # use thread to not block the simulation
    #     node_update_thread = Thread(target=update_node_power_model)
    #     node_update_thread.start()
    # self.updated_nodes.clear()


if __name__ == "__main__":
    main(result_csv="result.csv")
