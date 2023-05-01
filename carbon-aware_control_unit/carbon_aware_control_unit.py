from http_client import HTTPClient, HTTPClientError
import simpy
from typing import Optional


class Battery:
    """
    Initializes a Battery instance with the given initial state.

    Args:
        soc: The initial state of the battery's state of charge.
        min_soc: The minimum state of charge threshold for the battery.
        grid_charge: The initial state of the battery's grid charge level.
    """

    def __init__(self, soc: float = 0.0, min_soc: float = 0.0, grid_charge: float = 0.0) -> None:
        self.soc = soc
        self.min_soc = min_soc
        self.grid_charge = grid_charge


class CarbonAwareControlUnit:
    """
    Carbon-Aware Control Unit that manages power usage for a set of nodes.

    Args:
        server_address: The address of the server to connect to.
        nodes: A dictionary representing the nodes that the Control Unit
            manages, with node IDs as keys and node objects as values.

    Attributes:
        ci: The current carbon intensity in gCO2eq/kWh.
        solar: The current solar energy available in kWh.
        battery: The battery object that stores excess energy.
        power_modes: The list of available power modes for the nodes.
        nodes_power_mode: A dictionary mapping node IDs to their current power modes.
        nodes: A dictionary representing the nodes that the Control
            Unit manages, with node IDs as keys and node objects as values.
        client: The HTTPClient object used to communicate with the server.
        env: The SimPy environment used to simulate the Control Unit's behavior.
    """

    def __init__(self, server_address: str, nodes: dict) -> None:
        self.ci = 0.0
        self.solar = 0.0
        self.battery = Battery()
        self.power_modes = ['power-saving', 'normal', 'high performance']
        self.nodes_power_mode = {}
        self.nodes = nodes

        self.client = HTTPClient(server_address)

        self.env = simpy.Environment()
        self.env.process(self.scenario())


    def run_scenario(self, until: int):
        self.env.run(until=until)


    def scenario(self):
        """
        A SimPy process that runs the main control loop for the Carbon-Aware
        Control Unit. This process updates the Control Unit's values, sets the
        battery's minimum state of charge (SOC) based on the current time, and
        adjusts the power modes of the nodes based on the current carbon
        intensity and battery SOC.

        Yields:
            A SimPy timeout event that delays the process by one unit of time.
        """
        self.update_values()

        # Set the minimum SOC of the battery based on the current time
        if self.env.now < 60*36:
            self.set_battery(min_soc=0.3)
        else:
            self.set_battery(min_soc=0.6)

        # Adjust the power modes of the nodes based on the current carbon intensity and battery SOC
        if self.ci <= 200 or self.battery.soc > 0.8:
            self.set_node_power_mode(self.nodes['aws'], 'high performance')
            self.set_node_power_mode(self.nodes['raspi'], 'high performance')
        elif self.ci >= 250 and self.battery.soc < self.battery.min_soc:
            self.set_node_power_mode(self.nodes['aws'], 'power-saving')
            self.set_node_power_mode(self.nodes['raspi'], 'power-saving')
        else:
            self.set_node_power_mode(self.nodes['aws'], 'normal')
            self.set_node_power_mode(self.nodes['raspi'], 'normal')

        # Delay the process by one unit of time
        yield self.env.timeout(1)


    def update_values(self) -> None:
        """
        Updates all relevant attributes of the instance by by sending a GET request to the server.
        """
        self.battery.soc = self.client.get('/battery-soc')
        self.solar = self.client.get('/solar')
        self.ci = self.client.get('/ci')


    def set_battery(self, min_soc: Optional[float] = None , grid_charge: Optional[float] = None) -> None:
        """
        Sets the minimum SOC threshold and grid charge level of the battery by
        sending a put request to the server.

        Args:
            min_soc: The new minimum SOC threshold to set.
            grid_charge: The new grid charge level to set.
        """
        if not min_soc:
            min_soc = self.battery.min_soc
        if not grid_charge:
            grid_charge = self.battery.grid_charge
        try:
            self.client.put('/ves/battery', {'min_soc': min_soc, 'grid_charge': grid_charge})
            self.battery.min_soc = min_soc
            self.battery.grid_charge = grid_charge
        except HTTPClientError as e:
            print(e)


    def set_node_power_mode(self, node_id: int, power_mode: str) -> None:
        """
        Sets the power mode of a specified node by sending a PUT request to the server.

        Args:
            node_id: The ID of the node to set the power mode for.
            power_mode: The new power mode to set (must be one of
                'power-saving', 'normal', or 'high performance').
        """
        assert power_mode in self.power_modes
        try:
            self.client.put(f'/ves/nodes/{node_id}', {'power_mode': power_mode})
        except HTTPClientError as e:
            print(e)
