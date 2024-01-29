from __future__ import annotations
from typing import Optional
import threading
import time
from threading import Thread

from examples.controller_example import cacu_scenario
from vessim.sil import HttpClient


class LoopThread(threading.Thread):
    """Thread subclass that runs a target function until `stop()` is called.

    Also facilitates the propagation of exceptions to the main thread.

    Args:
        target_function: The function to be run in the thread.

    Attributes:
        target_function: The function to be run in the thread.
        stop_signal: An event that can be set to signal the
            thread to stop.
        exc: Variable that is set to propagate an exception to the main thread.
    """

    def __init__(self, target_function: callable[[], None], interval: float):
        super().__init__()
        self.target_function = target_function
        self.stop_signal = threading.Event()
        self.interval = interval
        self.exc = None

    def run(self):
        """Run the target function in a loop until the stop signal is set."""
        try:
            while not self.stop_signal.is_set():
                self.target_function()
                time.sleep(self.interval)
        except Exception as e:
            self.exc = e

    def stop(self):
        """Set the stop signal to stop the thread."""
        self.stop_signal.set()
        self.join()
        if self.exc:
            raise self.exc

    def propagate_exception(self):
        """Raises an exception if the target function raised an exception."""
        if self.exc:
            raise self.exc


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

        self.battery_soc = 0.0
        self.battery_min_soc = 0.0
        self.grid_charge = 0.0

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
        value = self.client.get("/battery-soc")["battery_soc"]
        if value:
            self.battery_soc = value
        value = self.client.get("/solar")["solar"]
        if value:
            self.solar = value
        value = self.client.get("/ci")["ci"]
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

        # Apply scenario logic
        scenario_data = cacu_scenario(
            sim_time,
            self.battery_min_soc,
            self.ci,
            self.node_ids
        )
        for node_id in self.node_ids:
            nodes_power_mode_new[node_id] = scenario_data["nodes_power_mode"][node_id]

        # Send battery values if changed
        battery_min_soc = scenario_data["battery_min_soc"]
        grid_charge = scenario_data["battery_grid_charge"]
        if (
            self.battery_min_soc != battery_min_soc or
            self.grid_charge != grid_charge
        ):
            Thread(target=self.send_battery, args=(battery_min_soc, grid_charge)).start()
            self.battery_min_soc = battery_min_soc
            self.grid_charge = grid_charge

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

    def send_battery(self, battery_min_soc, grid_charge) -> None:
        """Sends battery data to the energy system API."""
        body = {}
        if battery_min_soc:
            body["battery_min_soc"] = battery_min_soc
        if grid_charge:
            body["grid_charge"] = grid_charge
        self.client.put("/battery", body)

    def send_node_power_mode(self, node_id: int, power_mode: str) -> None:
        """Sends power mode data to the energy system API.

        Args:
            node_id: The ID of the node.
            power_mode: The power mode of the node to be set.

        """
        self.client.put(f"/api/nodes/{node_id}", {"power_mode": power_mode})
