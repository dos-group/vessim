from typing import Dict, List

from examples._data import load_solar_data, load_carbon_data
from vessim import TimeSeriesApi
from vessim.core.enviroment import Environment
from vessim.core.microgrid import Microgrid
from vessim.core.power_meters import MockPowerMeter
from vessim.core.storage import SimpleBattery, DefaultStoragePolicy
from vessim.cosim.actor import ComputingSystem, Generator
from vessim.cosim.controller import Controller

SIM_START = "2020-06-11 00:00:00"
DURATION = 3600 * 24 * 2  # two days
STORAGE = SimpleBattery(capacity=32 * 5 * 3600,  # 10Ah * 5V * 3600 := Ws
                        charge_level=32 * 5 * 3600 * .6,
                        min_soc=.6)
POLICY = DefaultStoragePolicy()


def main(carbon_aware: bool, result_csv: str):
    environment = Environment(sim_start=SIM_START)
    environment.add_grid_signal("carbon_intensity", TimeSeriesApi(load_carbon_data()))

    power_meters = [
        MockPowerMeter(name="mpm0", p=2.194),
        MockPowerMeter(name="mpm1", p=7.6)
    ]
    if carbon_aware:
        controller = ScenarioController(power_meters, STORAGE, POLICY)
    else:
        controller = Controller()
    microgrid = Microgrid(
        actors=[
            ComputingSystem(
                name="server",
                power_meters=power_meters
            ),
            Generator(
                name="solar",
                time_series_api=TimeSeriesApi(load_solar_data(sqm=0.4 * 0.5))
            ),
        ],
        storage=STORAGE,
        storage_policy=POLICY,
        controller=controller,
        zone="DE",
    )

    environment.add_microgrid(microgrid)
    environment.run(until=DURATION)

    microgrid.controller.monitor_to_csv(result_csv)


class ScenarioController(Controller):

    def __init__(self, mock_power_meters, battery, policy):
        super().__init__()
        self.mock_power_meters = mock_power_meters
        self.battery = battery
        self.policy = policy

    def step(self, time: int, p_delta: float, actors: Dict):
        """Performs a time step in the model."""
        # Apply scenario logic
        scenario_data = cacu_scenario(
            time,
            self.battery.soc(),
            self.grid_signals["carbon_intensity"].actual(self._clock.to_datetime(time), self.zone),
            [mpm.name for mpm in self.mock_power_meters]
        )
        self.policy.grid_power = scenario_data["grid_power"]
        self.battery.min_soc = scenario_data["battery_min_soc"]
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


# TODO refactor
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


if __name__ == "__main__":
    main(carbon_aware=True, result_csv="result.csv")
