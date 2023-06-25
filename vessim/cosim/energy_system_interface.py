from threading import Thread
import time

from vessim.core.storage import SimpleBattery, DefaultStoragePolicy
from vessim.cosim._util import VessimSimulator, VessimModel
from vessim.sil.http_client import HTTPClient, HTTPClientError
from vessim.sil.node import Node


class EnergySystemInterfaceSim(VessimSimulator):
    """Virtual Energy System (VES) simulator that executes the VES model."""

    META = {
        "type": "time-based",
        "models": {
            "EnergySystemInterface": {
                "public": True,
                "params": ["battery", "policy", "db_host", "api_host", "nodes"],
                "attrs": ["battery", "p_cons", "p_gen", "p_grid", "ci"],
            },
        },
    }

    def __init__(self) -> None:
        self.step_size = None
        super().__init__(self.META, _EnergySystemInterfaceModel)

    def init(self, sid, time_resolution, step_size, eid_prefix=None):
        self.step_size = step_size
        return super().init(sid, time_resolution, eid_prefix=eid_prefix)

    def finalize(self) -> None:
        """Stops the uvicorn server after the simulation has finished."""
        super().finalize()
        for model_instance in self.entities.values():
            model_instance.redis_docker.stop()

    def next_step(self, time):
        return time + self.step_size


class _EnergySystemInterfaceModel(VessimModel):
    """Software-in-the-Loop interface to the energy system simulation.

    TODO this class is still very specific to our paper use case and does not generalize
        well to other scenarios.

    Args:
        battery: SimpleBatteryModel used by the system.
        policy: The (dis)charging policy used to control the battery.
        nodes: List of physical or virtual computing nodes.
        api_server_address (optional): The server address and port for the API.
    """

    def __init__(
        self,
        nodes: list[Node],
        battery: SimpleBattery,
        policy: DefaultStoragePolicy,
        api_server_address: str,
        interval: int
    ):
        self.nodes = nodes
        self.updated_nodes = []
        self.battery = battery
        self.policy = policy
        self.p_cons = 0
        self.p_gen = 0
        self.p_grid = 0
        self.ci = 0
        self.http_client = HTTPClient(api_server_address)
        self.collector_thread = Thread(target=self._api_collector, args=(interval,))
        self.collector_thread.daemon = True
        self.collector_thread.start()

    def _api_collector(self, interval: int):
        while True:
            collection = self.http_client.get("/sim/collect-set")
            self.battery.min_soc = float(collection["battery_min_soc"])
            self.policy.grid_power = float(collection["battery_grid_charge"])
            nodes_power_mode = {int(k): v
                                for k, v in collection['nodes_power_mode'].items()}
            for node in self.nodes:
                if node.id in nodes_power_mode[node.id]:
                    node.power_mode = nodes_power_mode[node.id]
                    self.updated_nodes.append(node)
            time.sleep(interval)

    def step(self, time: int, inputs: dict) -> None:
        self.p_cons = inputs["p_cons"]
        self.p_gen = inputs["p_gen"]
        self.ci = inputs["ci"]
        self.p_grid = inputs["p_grid"]

        # update values to the api server
        def update_api_server():
            try:
                self.http_client.put("/sim/update", {
                    "solar": self.p_gen,
                    "ci": self.ci,
                    "battery_soc": self.battery.soc(),
                    "battery_min_soc": self.battery.min_soc,
                    "battery_grid_charge": self.policy.grid_power,
                    "nodes_power_mode": {node.id: node.power_mode
                                         for node in self.updated_nodes}
                })
            except HTTPClientError as e:
                print(e)
        # use thread to not slow down simulation
        api_server_update_thread = Thread(target=update_api_server)
        api_server_update_thread.start()

        # update power mode for the node remotely
        for node in self.updated_nodes:
            http_client = HTTPClient(f"{node.address}:{node.port}")

            def update_node_power_model():
                try:
                    http_client.put("/power_mode", {"power_mode": node.power_mode})
                except HTTPClientError as e:
                    print(e)
            # use thread to not slow down simulation
            node_update_thread = Thread(target=update_node_power_model)
            node_update_thread.start()

    def __del__(self) -> None:
        """Terminates the collector thread when the instance is deleted."""
        if self.collector_thread.is_alive():
            self.collector_thread.join()
