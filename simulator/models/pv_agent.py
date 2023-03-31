"""PV Agent module.

This module contains the agent for the PV controller.

Author: Marvin Steinke
"""

class PVAgent:
    """A class representing a PV agent for solar power production control. """

    def __init__(self, kW_conversion_factor: float = 1) -> None:
        """Initialize the PVAgent.

        Args:
            kW_conversion_factor (float, optional): Conversion factor to
            convert production to kilowatts. Default is 1.
        """
        self.kW_conversion_factor = kW_conversion_factor
        self.solar_power = 0

    def step(self, production: float) -> None:
        """Update the solar power based on the given production value and the
        conversion factor. Called every simulation step.

        Args:
            production (float): The solar power production in raw units.
        """
        self.solar_power = abs(production * self.kW_conversion_factor)
