import time
from threading import Thread
from typing import Optional

from vessim.sil.http_client import HttpClient
from vessim.sil.loop_thread import LoopThread
from simulated_cacu import cacu_scenario


class RemoteBattery:
    """Initializes a battery instance that holds info of the remote battery.

    Args:
        soc: The initial state of the battery's state of charge in %.
        min_soc: The minimum state of charge threshold for the battery in %.
        grid_charge: The power which the battery is charged with from the
            public grid in W.
    """

    def __init__(self, soc: float = 0.0, min_soc: float = 0.0,
                 grid_charge: float = 0.0) -> None:
        self.soc = soc
        self.min_soc = min_soc
        self.grid_charge = grid_charge


class CarbonAwareControlUnit:
    """The CACU uses the energy system for real-time carbon-aware scenarios.

    The Carbon Aware control unit uses an API server to communicate with vessim
    and retrieve real-time data about energy demand, solar power production,
    and grid carbon intensity via GET requests. Under predefined scenarios, the
    control unit sends SET requests to adjust vessim and computing system
    behavior. The Carbon Aware control unit's objective is to optimize the use
    of renewable energy sources and minimize carbon emissions by taking
    real-time decisions and actions based on these scenarios.

    Args:
        server_address: The address of the server to connect to.
        node_ids: A list of node_ids that the Control Unit manages.

    Attributes:
        power_modes: The list of available power modes for the nodes.
        nodes: A dictionary representing the nodes that the Control
            Unit manages, with node IDs as keys and node objects as values.
        client: The HttpClient object used to communicate with the server.
    """

    def __init__(self, server_address: str, node_ids: list[str]) -> None:
        self.power_modes = ["power-saving", "normal", "high performance"]
        self.node_ids = node_ids
        self.client = HttpClient(server_address)
        self.nodes_power_mode = {}
        self.battery = RemoteBattery()
        self.ci = 0.0
        self.solar = 0.0

        # Wait until vessim api server has started
        while True:
            try:
                self.client.get("/api/ci")
                break
            except:
                time.sleep(1)

    def run_scenario(
        self,
        rt_factor: float,
        step_size: int,
        update_interval: Optional[float]
    ):
        if update_interval is None:
            update_interval = rt_factor * step_size
        update_thread = LoopThread(self._update_getter, update_interval)
        update_thread.start()

        sim_time = 0
        while True:
            update_thread.propagate_exception()
            self.scenario_step(sim_time)
            sim_time += step_size
            time.sleep(rt_factor * step_size)

    def _update_getter(self) -> None:
        value = self.client.get("/api/battery-soc")["battery_soc"]
        if value:
            self.battery.soc = value
        value = self.client.get("/api/solar")["solar"]
        if value:
            self.solar = value
        value = self.client.get("/api/ci")["ci"]
        if value:
            self.ci = value

    def scenario_step(self, sim_time: int) -> None:
        """A Carbon-Aware Scenario.

        Scenario step for the Carbon-Aware Control Unit. This process updates
        the Control Unit's values, sets the battery's minimum state of charge
        (SOC) based on the current time, and adjusts the power modes of the
        nodes based on the current carbon intensity and battery SOC.

        Args:
            sim_time: Current simulation time.
        """
        nodes_power_mode_new = {}
        battery_new = RemoteBattery()

        # Apply scenario logic
        scenario_data = cacu_scenario(
            sim_time,
            self.battery.soc,
            self.ci,
            self.node_ids
        )
        battery_new.min_soc = scenario_data["battery_min_soc"]
        battery_new.grid_charge = scenario_data["battery_grid_charge"]
        for node_id in self.node_ids:
            nodes_power_mode_new[node_id] = scenario_data["nodes_power_mode"][node_id]

        # Send battery values if changed
        if (
            self.battery.min_soc != battery_new.min_soc or
            self.battery.grid_charge != battery_new.grid_charge
        ):
            Thread(target=self.send_battery, args=(battery_new,)).start()
            self.battery = battery_new

        # If node's power mode changed, send set request
        for node_id in self.node_ids:
            if (
                node_id not in self.nodes_power_mode or
                self.nodes_power_mode[node_id] != nodes_power_mode_new[node_id]
            ):
                Thread(
                    target=self.send_node_power_mode,
                    args=(node_id, nodes_power_mode_new[node_id])
                ).start()
                self.nodes_power_mode[node_id] = nodes_power_mode_new[node_id]

    def send_battery(self, battery: RemoteBattery) -> None:
        """Sends battery data to the energy system API.

        Args:
            battery: An object containing the battery data to be sent.
        """
        self.client.put("/api/battery", {
            "min_soc": battery.min_soc,
            "grid_charge": battery.grid_charge
        })

    def send_node_power_mode(self, node_id: int, power_mode: str) -> None:
        """Sends power mode data to the energy system API.

        Args:
            node_id: The ID of the node.
            power_mode: The power mode of the node to be set.

        """
        self.client.put(f"/api/nodes/{node_id}", {"power_mode": power_mode})
