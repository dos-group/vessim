import time
from vessim.sil.http_client import HTTPClient, HTTPClientError
from vessim.sil.stoppable_thread import StoppableThread
from threading import Thread
from typing import Dict, Optional


class RemoteBattery:
    """Initializes a battery instance that holds info of the remote battery.

    Args:
        soc: The initial state of the battery's state of charge in %.
        min_soc: The minimum state of charge threshold for the battery in %.
        grid_charge: The power which the battery is charged with from the
            public grid in W.
    """

    def __init__(self, soc: float = 0.0, min_soc: float = 0.0, grid_charge: float = 0.0) -> None:
        self.soc = soc
        self.min_soc = min_soc
        self.grid_charge = grid_charge


class CarbonAwareControlUnit:
    """The CACU uses the VESSIM API for real-time carbon-aware scenarios.

    The Carbon Aware control unit uses an API server to communicate with the
    VES simulation and retrieve real-time data about energy demand, solar power
    production, and grid carbon intensity via GET requests. Under predefined
    scenarios, the control unit sends SET requests to adjust the VES simulation
    and computing system behavior. The Carbon Aware control unit's objective is
    to optimize the use of renewable energy sources and minimize carbon
    emissions by taking real-time decisions and actions based on these
    scenarios.

    Args:
        server_address: The address of the server to connect to.
        nodes: A dictionary representing the nodes that the Control Unit
            manages, with node IDs as keys and node objects as values.

    Attributes:
        power_modes: The list of available power modes for the nodes.
        nodes: A dictionary representing the nodes that the Control
            Unit manages, with node IDs as keys and node objects as values.
        client: The HTTPClient object used to communicate with the server.
    """

    def __init__(self, server_address: str, nodes: dict) -> None:
        self.power_modes = ["power-saving", "normal", "high performance"]
        self.nodes = nodes
        self.client = HTTPClient(server_address)
        self.battery = RemoteBattery()
        self.ci = 0.0
        self.solar = 0.0

        while not self._is_server_ready():
            time.sleep(1)

    def _is_server_ready(self) -> bool:
        try:
            response = self.client.get('/api/ci')['ci']
            return True
        except HTTPClientError:
            return False

    def run_scenario(self, until: int, rt_factor: float, update_interval: Optional[float]):
        if update_interval is None:
            update_interval = rt_factor
        update_thread = StoppableThread(self._update_getter, update_interval)
        update_thread.start()

        for current_time in range(until):
            self.scenario_step(current_time)
            time.sleep(rt_factor)

        update_thread.stop()
        update_thread.join()

    def _update_getter(self) -> None:
        self.battery.soc = self.client.get("/api/battery-soc")["battery_soc"]
        self.solar = self.client.get("/api/solar")["solar"]
        self.ci = self.client.get("/api/ci")["ci"]

    def scenario_step(self, current_time) -> None:
        """A Carbon-Aware Scenario.

        Scenario step for the Carbon-Aware Control Unit. This process updates
        the Control Unit's values, sets the battery's minimum state of charge
        (SOC) based on the current time, and adjusts the power modes of the
        nodes based on the current carbon intensity and battery SOC.

        Args:
            current_time: Current simulation time.
        """
        nodes_power_mode = {}

        # Set the minimum SOC of the battery based on the current time
        if current_time < 60*36:
            self.battery.min_soc = 0.3
        else:
            self.battery.min_soc = 0.6

        # Adjust the power modes of the nodes based on the current carbon intensity and battery SOC
        if self.ci <= 200 or self.battery.soc > 0.8:
            nodes_power_mode[self.nodes["gcp"]] = "high performance"
            nodes_power_mode[self.nodes["raspi"]] = "high performance"
        elif self.ci >= 250 and self.battery.soc < self.battery.min_soc:
            nodes_power_mode[self.nodes["gcp"]] = "power-saving"
            nodes_power_mode[self.nodes["raspi"]] = "power-saving"
        else:
            nodes_power_mode[self.nodes["gcp"]] = "normal"
            nodes_power_mode[self.nodes["raspi"]] = "normal"

        # Send and forget
        Thread(target=self.send_battery, args=(self.battery,)).start()
        Thread(target=self.send_nodes_power_mode, args=(nodes_power_mode,)).start()

    def send_battery(self, battery: RemoteBattery) -> None:
        """Sends battery data to the VES API.

        Args:
            battery: An object containing the battery data to be sent.
        """
        self.client.put("/api/battery", {"min_soc": battery.min_soc, "grid_charge": battery.grid_charge})

    def send_nodes_power_mode(self, nodes_power_mode: Dict[int, str]) -> None:
        """Sends power mode data for nodes to the VES API.

        Args:
            nodes_power_mode: A dictionary containing node IDs as keys and
                their respective power modes as values.

        """
        # TODO send new(!) power modes as single put request
        for node_id, power_mode in nodes_power_mode.items():
            try:
                self.client.put(f"/api/nodes/{node_id}", {"power_mode": power_mode})
            except HTTPClientError:
                print(f"Could not update power mode of node {node_id}")
