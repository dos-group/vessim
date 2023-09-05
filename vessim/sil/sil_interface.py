from threading import Thread
from typing import List, Optional

from vessim.core.storage import SimpleBattery, DefaultStoragePolicy, StoragePolicy
from vessim.cosim._util import VessimSimulator, VessimModel, simplify_inputs
from vessim.sil.api_server import ApiServer, VessimApi
from vessim.sil.http_client import HttpClient
from vessim.sil.node import Node
from vessim.sil.loop_thread import LoopThread


class SilInterfaceSim(VessimSimulator):
    """Software-in-the-Loop (SiL) interface simulator that executes the model."""

    META = {
        "type": "time-based",
        "models": {
            "SilInterface": {
                "public": True,
                "any_inputs": True,
                "params": [
                    "nodes",
                    "battery",
                    "policy",
                    "collection_interval",
                    "api_host",
                    "api_port"
                ],
                "attrs": []
            },
        },
    }

    def __init__(self) -> None:
        self.step_size = None
        super().__init__(self.META, _SilInterfaceModel)

    def init(self, sid, time_resolution, step_size, eid_prefix=None):
        self.step_size = step_size
        return super().init(sid, time_resolution, eid_prefix=eid_prefix)

    def finalize(self) -> None:
        """Stops the api server and the collector thread when the simulation finishes."""
        super().finalize()
        for model_instance in self.entities.values():
            model_instance.collector_thread.stop() # type: ignore
            model_instance.collector_thread.join() # type: ignore
            model_instance.http_client.put("/shutdown") # type: ignore
            model_instance.api_server.terminate() # type: ignore
            model_instance.api_server.join() # type: ignore

    def next_step(self, time):
        return time + self.step_size


class _SilInterfaceModel(VessimModel):
    """Software-in-the-Loop interface to the energy system simulation.

    TODO this class is still very specific to our paper use case and does not
    generalize well to other scenarios.

    Args:
        nodes: List of vessim SiL nodes.
        battery: SimpleBattery battery used by the system.
        policy: The (dis)charging policy used to control the battery.
        nodes: List of physical or virtual computing nodes.
        collection_interval: Interval in which `/sim/collet-set` in fetched from
            the API server.
        api_host: Server address for the API.
        api_port: Server port for the API.
    """

    def __init__(
        self,
        nodes: List[Node],
        battery: SimpleBattery,
        collection_interval: float,
        policy: Optional[StoragePolicy] = None,
        api_host: str = "127.0.0.1",
        api_port: int = 8000
    ):
        self.nodes = nodes
        self.updated_nodes: List[Node] = []
        self.battery = battery
        self.policy = policy if policy is not None else DefaultStoragePolicy()
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

    def step(self, time: int, inputs: dict) -> None:
        self.collector_thread.propagate_exception()
        inputs = simplify_inputs(inputs)
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

