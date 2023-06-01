from simulator.single_model_simulator import SingleModelSimulator
from simulator.power_meter import PowerMeter
from typing import List

META = {
    "type": "time-based",
    "models": {
        "ComputingSystem": {
            "public": True,
            "params": ["power_meters"],
            "attrs": ["p_cons"],
        },
    },
}


class ComputingSystem(SingleModelSimulator):
    """Computing System simulator that executes its model."""

    def __init__(self):
        super().__init__(META, ComputingSystem)

    def create(self, num, model, *args, **kwargs):
        if num != 1:
            raise ValueError("Only one instance of the ComputingSystem can exist.")

        # access power_meters from kwargs
        power_meters = kwargs.get("power_meters")
        if not power_meters:
            raise ValueError("At least one power meter needs to be specified.")

        return super().create(num, model, *args, **kwargs)


class ComputingSystemModel:
    """Model of the computing system.

    This model considers the power usage effectiveness (PUE) and power
    consumption of a list of power meters.

    Attributes:
        power_meters: A list of PowerMeter objects
            representing power meters in the system.
        pue: The power usage effectiveness of the system.
        p_cons: The power consumption of the system, computed in the step
            method.
    """

    def __init__(self, power_meters: List[PowerMeter], pue: float):
        self.power_meters = power_meters
        self.p_cons = 0
        self.pue = pue

    def step(self):
        """Updates the power consumption of the system.

        The power consumption is calculated as the product of the PUE and the
        sum of the node power of all power meters.
        """
        self.p_cons = self.pue * sum(pm() for pm in self.power_meters)
