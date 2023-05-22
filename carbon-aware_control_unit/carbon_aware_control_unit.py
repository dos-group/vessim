from ..lib.http_client import HTTPClient
import simpy
from typing import Dict


class RemoteBattery:
    """Initializes a battery instance that holds some info of the remote battery.

    Args:
        soc: The initial state of the battery's state of charge in %.
        min_soc: The minimum state of charge threshold for the battery in %.
        grid_charge: The power which the battery is charged with from the public grid in W.
    """

    def __init__(self, soc: float = 0.0, min_soc: float = 0.0, grid_charge: float = 0.0) -> None:
        self.soc = soc
        self.min_soc = min_soc
        self.grid_charge = grid_charge


class CarbonAwareControlUnit:
    """The Carbon Aware Control Unit uses the VESSIM API to execute real-time carbon-aware scenarios.

    The Carbon Aware control unit uses an API server to communicate with the VES
    simulation and retrieve real-time data about energy demand, solar power
    production, and grid carbon intensity via GET requests. Under predefined
    scenarios, the control unit sends SET requests to adjust the VES simulation and
    computing system behavior. The Carbon Aware control unit's objective is to
    optimize the use of renewable energy sources and minimize carbon emissions by
    taking real-time decisions and actions based on these scenarios.

    Args:
        server_address: The address of the server to connect to.
        nodes: A dictionary representing the nodes that the Control Unit
            manages, with node IDs as keys and node objects as values.

    Attributes:
        power_modes: The list of available power modes for the nodes.
        nodes: A dictionary representing the nodes that the Control
            Unit manages, with node IDs as keys and node objects as values.
        client: The HTTPClient object used to communicate with the server.
        env: The SimPy environment used to simulate the Control Unit's behavior.
    """

    def __init__(self, server_address: str, nodes: dict) -> None:
        self.power_modes = ['power-saving', 'normal', 'high performance']
        self.nodes = nodes

        self.client = HTTPClient(server_address)

        self.env = simpy.Environment()
        self.env.process(self.scenario())


    def run_scenario(self, until: int):
        self.env.run(until=until)


    def scenario(self):
        """A Carbon-Aware Scenario.

        A SimPy process that runs the main control loop for the Carbon-Aware
        Control Unit. This process updates the Control Unit's values, sets the
        battery's minimum state of charge (SOC) based on the current time, and
        adjusts the power modes of the nodes based on the current carbon
        intensity and battery SOC.

        Yields:
            A SimPy timeout event that delays the process by one unit of time.
        """
        battery = RemoteBattery(soc=self.client.get('/battery-soc'))
        solar = self.client.get('/solar')
        ci = self.client.get('/ci')
        nodes_power_mode = {}

        # Set the minimum SOC of the battery based on the current time
        if self.env.now < 60*36:
            battery.min_soc = 0.3
        else:
            battery.min_soc = 0.6

        # Adjust the power modes of the nodes based on the current carbon intensity and battery SOC
        if ci <= 200 or battery.soc > 0.8:
            nodes_power_mode[self.nodes['aws']] = 'high performance'
            nodes_power_mode[self.nodes['raspi']] = 'high performance'
        elif ci >= 250 and battery.soc < battery.min_soc:
            nodes_power_mode[self.nodes['aws']] = 'power-saving'
            nodes_power_mode[self.nodes['raspi']] = 'power-saving'
        else:
            nodes_power_mode[self.nodes['aws']] = 'normal'
            nodes_power_mode[self.nodes['raspi']] = 'normal'

        # Delay the process by one unit of time
        self.send_battery(battery)
        self.send_nodes_power_mode(nodes_power_mode)

        yield self.env.timeout(1)


    def send_battery(self, battery: Battery) -> None:
        """Sends battery data to the VES API.

        Args:
            battery: An object containing the battery data to be sent.
        """
        self.client.put('/ves/battery', {'min_soc': battery.min_soc, 'grid_charge': battery.grid_charge})


    def send_nodes_power_mode(self, nodes_power_mode: Dict[int, str]) -> None:
        """Sends power mode data for nodes to the VES API.

        Args:
            nodes_power_mode: A dictionary containing node IDs as keys and their respective power modes as values.

        """
        for node_id, power_mode in nodes_power_mode.items():
            self.client.put(f'/ves/nodes/{node_id}', {'power_mode': power_mode})
