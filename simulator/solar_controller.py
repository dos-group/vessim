from vessim.core import VessimSimulator, VessimModel

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


class SolarController(VessimSimulator):
    """Solar Controller.

    Acts as medium between Solar CSV module and ecovisor or direct consumer since producer
    is only a csv generator.
    """

    def __init__(self):
        super().__init__(META, SolarAgent)

    def next_step(self, time):
        return None


class SolarAgent(VessimModel):
    """Class representing a solar agent for solar power production control.

    Args:
        scaling_factor: Scaling factor, e.g. for converting from mW to kW.
        Default is 1.
    """

    def __init__(self, scaling_factor: float = 1) -> None:
        self.scaling_factor = scaling_factor
        self.solar = 0.0

    def step(self, time: int, inputs: dict) -> None:
        """Compute new production value.

        Update the solar power based on the given production value and the
        scaling factor. Called every simulation step.
        """
        self.solar = abs(inputs["solar"] * self.scaling_factor)
