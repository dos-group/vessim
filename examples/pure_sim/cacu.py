from vessim.cosim._util import VessimSimulator, VessimModel, simplify_inputs
from vessim.core.consumer import MockPowerMeter
from vessim.core.storage import SimpleBattery, DefaultStoragePolicy

from typing import List, Dict


class CacuSim(VessimSimulator):
    """Carbon-Aware Control Unit simulator that executes its model."""

    META = {
        "type": "time-based",
        "models": {
            "Cacu": {
                "public": True,
                "any_inputs": True,
                "params": ["mock_power_meters", "battery", "policy"],
                "attrs": [],
            },
        },
    }

    def __init__(self):
        self.step_size = None
        super().__init__(self.META, _CacuModel)

    def init(self, sid, time_resolution, step_size, eid_prefix=None):
        self.step_size = step_size
        return super().init(sid, time_resolution, eid_prefix=eid_prefix)

    def next_step(self, time):
        return time + self.step_size


class _CacuModel(VessimModel):
    """Model for the CACU, *exclusively* for simulated scenarios.

    This class is used to model a system which utilizes a set of power meters
    and a storage mechanism. The power meters' mode and state of storage
    changes based on the pre defined scenario in `step()`, related to time,
    carbon intensity and storage state.

    Attributes:
        mock_power_meters: A list of mock power meters used in the model.
        battery: A storage object used in the model.
    """

    def __init__(
        self,
        mock_power_meters: List[MockPowerMeter],
        storage: SimpleBattery,
        policy: DefaultStoragePolicy
    ):
        self.mock_power_meters = mock_power_meters
        self.storage = storage
        self.policy = policy

    def step(self, time: int, inputs: Dict) -> None:
        """Performs a time step in the model."""
        inputs = simplify_inputs(inputs)
        if time > 3600 * 30 and self.storage.soc() >= .6:
            self.storage.min_soc = .6
        else:
            self.storage.min_soc = .3

        if inputs["ci"] <= 200 and self.storage.soc() < .6:
            self.policy.grid_power = 20
        else:
            self.policy.grid_power = 0

        for power_meter in self.mock_power_meters:
            if inputs["ci"] <= 200 or self.storage.soc() > .8:
                power_meter.factor = 1
            elif inputs["ci"] >= 250 and self.storage.soc() < .6:
                power_meter.factor = .5
            else:
                power_meter.factor = .7
