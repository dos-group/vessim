from typing import Dict, List

from examples.basic_example import SIM_START, STORAGE, DURATION, SOLAR_DATASET, \
    CARBON_DATASET
from vessim.core import HistoricalApi
from vessim.cosim import ComputingSystem, Generator, Monitor, Controller, Microgrid, \
    Environment, DefaultStoragePolicy, MockPowerMeter

POLICY = DefaultStoragePolicy()
POWER_MODES = {  # according to paper
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


def main(result_csv: str):
    environment = Environment(sim_start=SIM_START)

    solar_api = HistoricalApi.from_dataset(
        SOLAR_DATASET,
        "./data",
        scale=0.4 * 0.5 * .17,
        start_time="2020-06-01 00:00:00",
    )

    carbon_api = HistoricalApi.from_dataset(CARBON_DATASET, "./data")

    environment.add_grid_signal("carbon_intensity", carbon_api)

    power_meters = [
        MockPowerMeter(name="mpm0", p=2.194),
        MockPowerMeter(name="mpm1", p=7.6)
    ]
    monitor = Monitor(step_size=60)
    carbon_aware_controller = CarbonAwareController(
        step_size=60,
        power_meters=power_meters,
        battery=STORAGE,
        policy=POLICY,
    )
    microgrid = Microgrid(
        actors=[
            ComputingSystem(
                name="server",
                step_size=60,
                power_meters=power_meters
            ),
            Generator(name="solar", step_size=60, api=solar_api),
        ],
        storage=STORAGE,
        storage_policy=POLICY,
        controllers=[monitor, carbon_aware_controller],  # first executes monitor, then controller
        zone="DE",
    )

    environment.add_microgrid(microgrid)
    environment.run(until=DURATION)
    monitor.monitor_log_to_csv(result_csv)


class CarbonAwareController(Controller):
    def __init__(self, step_size, power_meters, battery, policy):
        super().__init__(step_size)
        self.power_meters = power_meters
        self.battery = battery
        self.policy = policy

    def step(self, time: int, p_delta: float, actors: Dict):
        """Performs a time step in the model."""
        new_state = cacu_scenario(
            time=time,
            battery_soc=self.battery.soc(),
            ci=self.grid_signals["carbon_intensity"].actual(self.clock.to_datetime(time), self.microgrid.zone),
            node_names=[node.name for node in self.power_meters],
        )
        self.policy.grid_power = new_state["grid_power"]
        self.battery.min_soc = new_state["battery_min_soc"]
        assert {"mpm0", "mpm1"}.issubset({mpm.name for mpm in self.power_meters})
        for node in self.power_meters:
            node.set_power(POWER_MODES[node.name][new_state["nodes_power_mode"][node.name]])


def cacu_scenario(
    time: int,
    battery_soc: float,
    ci: float,
    node_names: List[str]
) -> dict:
    """Calculate the power mode settings for nodes based on a scenario.

    This function simulates the decision logic of a Carbon-Aware Control Unit
    (CACU) by considering battery state-of-charge (SOC), time, and carbon
    intensity (CI).

    Args:
        time: Time in minutes since some reference point or start.
        battery_soc: Current state of charge of the battery.
        ci: Current carbon intensity.
        node_names: A list of node IDs for which the power mode needs to be
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
    new_state = {}
    time_of_day = time % (3600 * 24)
    if 11 * 3600 <= time_of_day < 24 * 3600 and battery_soc >= 0.6:
        new_state["battery_min_soc"] = .6
    else:
        new_state["battery_min_soc"] = .3

    new_state["grid_power"] = 20 if ci <= 200 and battery_soc < .6 else 0
    new_state["nodes_power_mode"] = {}
    for node_name in node_names:
        if ci <= 200 or battery_soc > .8:
            new_state["nodes_power_mode"][node_name] = "high performance"
        elif ci >= 250 and battery_soc < .6:
            new_state["nodes_power_mode"][node_name] = "power-saving"
        else:
            new_state["nodes_power_mode"][node_name] = "normal"
    return new_state


if __name__ == "__main__":
    main(result_csv="result.csv")
