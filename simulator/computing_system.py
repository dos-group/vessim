from vessim.core import VessimSimulator, VessimModel
from simulator.power_meter import PowerMeter
from typing import List


class ComputingSystemSim(VessimSimulator):
    """Computing System simulator that executes its model."""

    META = {
        "type": "time-based",
        "models": {
            "ComputingSystemModel": {
                "public": True,
                "params": ["power_meters", "pue"],
                "attrs": ["p_cons"],
            },
        },
    }

    def __init__(self):
        self.step_size = None
        super().__init__(self.META, ComputingSystemModel)

    def init(self, sid, time_resolution, step_size, eid_prefix=None):
        self.step_size = step_size
        return super().init(sid, time_resolution, eid_prefix=eid_prefix)

    def next_step(self, time):
        return time + self.step_size


class ComputingSystemModel(VessimModel):
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
        self.pue = pue
        self.p_cons = 0.0

    def step(self, time: int, inputs: dict) -> None:
        """Updates the power consumption of the system.

        The power consumption is calculated as the product of the PUE and the
        sum of the node power of all power meters.
        """
        self.p_cons = self.pue * sum(pm.measure() for pm in self.power_meters)
