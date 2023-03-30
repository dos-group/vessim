"""Carbon Agent module.

This module contains the agent to the carbon controller.

Author: Marvin Steinke
"""

class CarbonAgent:
    """A class to represent the Carbon Agent."""

    def __init__(self, carbon_conversion_factor: float = 1.0) -> None:
        """Initialize the CarbonAgent instance.

        Args:
            carbon_conversion_factor (float, optional): The carbon conversion
            factor. Defaults to 1.0. Can be used to convert the carbon
            intensity units in the CSV file (e.g. from lb to kg:
            conversion_factor~=0,453592).
        """
        self.carbon_conversion_factor = carbon_conversion_factor
        self.carbon_intensity = 0

    def step(self, intensity_input: float) -> None:
        """Calculate the carbon intensity based on the input intensity and the
        conversion factor. Called every simulation step.

        Args:
            intensity_input (float): The input intensity value.
        """
        self.carbon_intensity = abs(intensity_input * self.carbon_conversion_factor)
