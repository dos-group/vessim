"""Co-simulation example with software-in-the-loop.

This scenario builds on `controller_example.py` but connects to a real computing system
through software-in-the-loop integration as described in our paper:
- 'Software-in-the-loop simulation for developing and testing carbon-aware applications'.
  [under review]

This is example experimental and documentation is still in progress.
"""
from threading import Thread
from typing import List, Optional, Dict

from _data import load_carbon_data, load_solar_data
from controller_example import (
    SIM_START,
    STORAGE,
    DURATION, POLICY
)
from vessim import TimeSeriesApi
from vessim.core.enviroment import Environment
from vessim.core.microgrid import Microgrid
from vessim.core.storage import SimpleBattery, StoragePolicy, DefaultStoragePolicy
from vessim.cosim.actor import ComputingSystem, Generator
from vessim.cosim.controller import Controller, Monitor
from vessim.cosim.util import disable_mosaik_warnings, Clock
from vessim.sil.api_server import ApiServer, VessimApi
from vessim.sil.http_client import HttpClient
from vessim.sil.loop_thread import LoopThread
from vessim.sil.node import Node
from vessim.sil.power_meter import HttpPowerMeter

RT_FACTOR = 1/60  # 1 wall-clock second ^= 60 sim seconds
GCP_ADDRESS = "http://35.198.148.144"
RASPI_ADDRESS = "http://192.168.207.71"
disable_mosaik_warnings(behind_threshold=0.01)


def main(result_csv: str):
    environment = Environment(sim_start=SIM_START)
    environment.add_grid_signal("carbon_intensity", TimeSeriesApi(load_carbon_data()))

    # Initialize nodes
    nodes = [
        Node(address=GCP_ADDRESS, id="gcp"),
        Node(address=RASPI_ADDRESS, id="raspi")
    ]
    power_meters = [
        HttpPowerMeter(name="mpm0", interval=1, server_address=GCP_ADDRESS),
        HttpPowerMeter(name="mpm1", interval=1, server_address=RASPI_ADDRESS),
    ]
    monitor = Monitor(step_size=60)
    carbon_aware_controller = SilController(
        step_size=60,

        nodes=nodes, battery=STORAGE, collection_interval=1,
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
    environment.run(until=DURATION, rt_factor=RT_FACTOR)
    monitor.monitor_log_to_csv(result_csv)


class SilController(Controller):

    def __init__(
        self,
        step_size: int,
        nodes: List[Node],
        collection_interval: float,
        battery: SimpleBattery,
        policy: StoragePolicy,
        api_host: str = "127.0.0.1",
        api_port: int = 8000,
    ):
        super().__init__(step_size=step_size)
        self.nodes = nodes
        self.updated_nodes: List[Node] = []
        self.battery = battery
        self.policy = policy
        self.p_cons = 0
        self.p_gen = 0
        self.p_grid = 0
        self.ci = 0

        # start server process
        self.api_server = ApiServer(VessimApi, api_host, api_port)
        self.api_server.start()
        self.api_server.wait_for_startup_complete()

        # init server values and wait for put request confirmation
        self.http_client = HttpClient(f"http://{api_host}:{api_port}")
        self.http_client.put("/sim/update", {
            "solar": self.p_gen,
            "ci": self.ci,
            "battery_soc": self.battery.soc(),
        })

        self.collector_thread = LoopThread(self._api_collector, collection_interval)
        self.collector_thread.start()

    def start(self, microgrid: "Microgrid", clock: Clock, grid_signals: Dict):
        pass

    def step(self, time: int, p_delta: float, actors: Dict) -> None:
        self.collector_thread.propagate_exception()
        self.p_cons = inputs["p_cons"]
        self.p_gen = inputs["p_gen"]
        self.ci = inputs["ci"]
        self.p_grid = inputs["p_grid"]

        # update values to the api server
        def update_api_server():
            self.http_client.put("/sim/update", {
                "solar": self.p_gen,
                "ci": self.ci,
                "battery_soc": self.battery.soc(),
            })

        # use thread to not slow down simulation
        api_server_update_thread = Thread(target=update_api_server)
        api_server_update_thread.start()

        # update power mode for the node remotely
        for node in self.updated_nodes:
            http_client = HttpClient(f"{node.address}:{node.port}")

            def update_node_power_model():
                http_client.put("/power_mode", {"power_mode": node.power_mode})

            # use thread to not slow down simulation
            node_update_thread = Thread(target=update_node_power_model)
            node_update_thread.start()
        self.updated_nodes.clear()

    def finalize(self) -> None:
        """This method can be overridden clean-up after the simulation finished."""
        self.collector_thread.stop()
        self.collector_thread.join()
        self.http_client.put("/shutdown")
        self.api_server.terminate()
        self.api_server.join()

    def _api_collector(self):
        """Collects data from the API server.

        The endpoint "/sim/collect-set" yields the 3 fields `battery_min_soc`,
        `battery_grid_charge` and `nodes_power_mode`. Since multiple set
        request of these values from different actors are possible, each of
        these fields is a list of dictionaries with the timestamp (formated as
        `datetime.now().isoformat()`) and the set value at that time.

        TODO implement user defined collection method. Current static
        collection method: most recent entry.
        """
        collection = self.http_client.get("/sim/collect-set")

        # The value of the keys is None by default if no set request was made
        # by an actor => Check if not None first.
        if collection["battery_min_soc"]:
            # The newest entry is the one with the highest iso timestamp.
            newest_key = max(collection["battery_min_soc"].keys())
            self.battery.min_soc = float(collection["battery_min_soc"][newest_key])

        if collection["battery_grid_charge"]:
            newest_key = max(collection["battery_grid_charge"].keys())
            self.policy.grid_power = float(collection["battery_grid_charge"][newest_key])

        if collection["nodes_power_mode"]:
            newest_key = max(collection["nodes_power_mode"].keys())
            nodes_power_mode = dict(collection['nodes_power_mode'][newest_key].items())
            # nodes_power_mode looks e.g. like {"gcp": "normal",...}
            # Loop through all nodes,
            for node in self.nodes:
                if node.id in nodes_power_mode:
                    # update the power_mode if it changed
                    node.power_mode = nodes_power_mode[node.id]
                    # and save whatever node had its powermode updated to
                    # remotely update only that nodes' power mode in step().
                    self.updated_nodes.append(node)


if __name__ == "__main__":
    main(result_csv="result.csv")
