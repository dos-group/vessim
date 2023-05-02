import mosaik_api
from simulator.single_model_simulator import SingleModelSimulator

META = {
    "type": "event-based",
    "models": {
        "SolarAgent": {
            "public": True,
            "params": ["scaling_factor"],
            "attrs": ["solar"],
        },
    },
}


class SolarController(SingleModelSimulator):
    """Solar Controller.

    Acts as medium between Solar CSV module and ecovisor or direct consumer since producer
    is only a csv generator.

    """

    def __init__(self):
        super().__init__(META, SolarAgent)


class SolarAgent:
    """Class representing a solar agent for solar power production control.

    Args:
        scaling_factor: Scaling factor, e.g. for converting from mW to kW.
        Default is 1.
    """

    def __init__(self, scaling_factor: float = 1) -> None:
        self.scaling_factor = scaling_factor
        self.solar = 0.0
        self.production = 0.0

    def step(self) -> None:
        """Update the solar power based on the given production value and the
        scaling factor. Called every simulation step.
        """
        self.solar = abs(self.production * self.scaling_factor)


def main():
    """Main function that starts the simulation."""
    return mosaik_api.start_simulation(SolarController())
