from typing import List, Dict

from vessim.core.consumer import MockPowerMeter
from vessim.core.storage import SimpleBattery, DefaultStoragePolicy
from vessim.cosim._util import VessimSimulator, VessimModel, simplify_inputs


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
        #power_modes = {
        #    "high performance": 1.,
        #    "normal": .7,
        #    "power-saving": .5
        #}
        ## update factor of mpms based on scenario logic
        #for mpm in self.mock_power_meters:
        #    if mpm.name in scenario_data["nodes_power_mode"].keys():
        #        mpm.factor = power_modes[scenario_data["nodes_power_mode"][mpm.name]]
        power_modes = {
            "mpm0": {
                "high performance": 2.964,
                "normal": 2.194,
                "power-saving": 1.781
            },
            "mpm1": {
                "high performance": 8.8,
                "normal": 7.6,
                "power-saving": 6.8
            }
        }
        assert set(["mpm0", "mpm1"]).issubset(
            {mpm.name for mpm in self.mock_power_meters}
        )
        for mpm in self.mock_power_meters:
            mpm.p = power_modes[mpm.name][scenario_data["nodes_power_mode"][mpm.name]]


def cacu_scenario(
    time: int,
    battery_soc: float,
    ci: float,
    node_ids: List[str]
) -> dict:
    """Calculate the power mode settings for nodes based on a scenario.

    This function simulates the decision logic of a Carbon-Aware Control Unit
    (CACU) by considering battery state-of-charge (SOC), time, and carbon
    intensity (CI).

    Args:
        time: Time in minutes since some reference point or start.
        battery_soc: Current state of charge of the battery.
        ci: Current carbon intensity.
        node_ids: A list of node IDs for which the power mode needs to be
            determined.

    Returns:
        A dictionary containing:
            - battery_min_soc: Updated minimum state of charge value based on
              the given time.
            - grid_power: Power to be drawn from the grid.
            - nodes_power_mode: A dictionary with node IDs as keys and their
              respective power modes ('high performance', 'normal', or
              'power-saving') as values.
    """
    data = {}

    time_of_day = time % (3600 * 24)
    if 11 * 3600 <= time_of_day < 24 * 3600 and battery_soc >= 0.6:
        data["battery_min_soc"] = .6
    else:
        data["battery_min_soc"] = .3

    data["grid_power"] = 20 if ci <= 200 and battery_soc < .6 else 0
    data["nodes_power_mode"] = {}
    for node_id in node_ids:
        if ci <= 200 or battery_soc > .8:
            data["nodes_power_mode"][node_id] = "high performance"
        elif ci >= 250 and battery_soc < .6:
            data["nodes_power_mode"][node_id] = "power-saving"
        else:
            data["nodes_power_mode"][node_id] = "normal"
    return data
