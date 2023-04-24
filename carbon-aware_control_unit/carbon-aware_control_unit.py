import sys
from http_client import HTTPClient, HTTPClientError
import simpy


class Battery:
    """
    Initializes a Battery instance with the given initial state.

    Args:
        soc: The initial state of the battery's state of charge (default 0.0).
        min_soc: The minimum state of charge threshold for the battery (default 0.0).
        grid_charge: The initial state of the battery's grid charge level (default 0.0).
    """

    def __init__(self, soc: float = 0.0, min_soc: float = 0.0, grid_charge: float = 0.0) -> None:
        self.soc = soc
        self.min_soc = min_soc
        self.grid_charge = grid_charge


class CarbonAwareControlUnit:
    """
    Initializes a CarbonAwareControlUnit instance with the given server address.

    Args:
        server_address: The address of the server to connect to.
    """

    def __init__(self, server_address: str) -> None:
        self.ci = 0.0
        self.solar = 0.0
        self.battery = Battery()
        self.power_modes = ['power-saving', 'normal', 'high performance']
        # node id -> power mode
        self.nodes_power_mode = {}

        self.client = HTTPClient(server_address)

        self.env = simpy.Environment()


    def update_ci(self) -> None:
        """
        Updates the CarbonIntensity attribute of the instance by sending a GET request to the server.
        """
        try:
            value = self.client.GET('/ci')
            assert isinstance(value, float)
            self.ci = value
        except HTTPClientError as e:
            print(e)


    def update_solar(self) -> None:
        """
        Updates the Solar attribute of the instance by sending a GET request to the server.
        """
        try:
            value = self.client.GET('/solar')
            assert isinstance(value, float)
            self.solar = value
        except HTTPClientError as e:
            print(e)


    def update_battery_soc(self) -> None:
        """
        Updates the State of Charge (SOC) attribute of the battery by sending a GET request to the server.
        """
        try:
            value = self.client.GET('/battery-soc')
            assert isinstance(value, float)
            self.battery.soc = value
        except HTTPClientError as e:
            print(e)


    def update_values(self) -> None:
        """
        Updates all relevant attributes of the instance by calling the corresponding update methods.
        """
        self.update_battery_soc()
        self.update_ci()
        self.update_solar()


    def set_battery(self, min_soc: float, grid_charge: float) -> None:
        """
        Sets the minimum SOC threshold and grid charge level of the battery by sending a PUT request to the server.

        Args:
            min_soc: The new minimum SOC threshold to set.
            grid_charge: The new grid charge level to set.
        """
        try:
            self.client.PUT('/ves/battery', {'min_soc': min_soc, 'grid_charge': grid_charge})
        except HTTPClientError as e:
            print(e)


    def set_node_power_mode(self, node_id: int, power_mode: str) -> None:
        """
        Sets the power mode of a specified node by sending a PUT request to the server.

        Args:
            node_id: The ID of the node to set the power mode for.
            power_mode: The new power mode to set (must be one of 'power-saving', 'normal', or 'high performance').
        """
        assert power_mode in self.power_modes
        try:
            self.client.PUT(f'/ves/nodes/{node_id}', {'power_mode': power_mode})
        except HTTPClientError as e:
            print(e)


if __name__ == '__main__':

    # Get server address from command line arguments, default to http://localhost
    if len(sys.argv) > 1:
        server_address = sys.argv[1]
    else:
        server_address = 'http://localhost'

    CarbonAwareControlUnit(server_address)
