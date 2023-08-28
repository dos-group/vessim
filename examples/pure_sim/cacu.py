from vessim.cosim._util import VessimSimulator, VessimModel, simplify_inputs
from vessim.core.consumer import MockPowerMeter
from vessim.core.storage import SimpleBattery, DefaultStoragePolicy
from examples.pure_sim.cosim_example import cacu_scenario

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
        battery: SimpleBattery,
        policy: DefaultStoragePolicy
    ):
        self.mock_power_meters = mock_power_meters
        self.battery = battery
        self.policy = policy

    def step(self, time: int, inputs: Dict) -> None:
        """Performs a time step in the model."""
        inputs = simplify_inputs(inputs)

        # Apply scenario logic
        scenario_data = cacu_scenario(
            time,
            self.battery.soc(),
            inputs["ci"],
            [mpm.name for mpm in self.mock_power_meters]
        )
        self.policy.grid_power = scenario_data["grid_power"]
        self.battery.min_soc = scenario_data["battery_min_soc"]
        power_modes = {
            "high performance": 1.,
            "normal": .7,
            "power-saving": .5
        }
        # update factor of mpms based on scenario logic
        for mpm in self.mock_power_meters:
            if mpm.name in scenario_data["nodes_power_mode"].keys():
                mpm.factor = power_modes[scenario_data["nodes_power_mode"][mpm.name]]

