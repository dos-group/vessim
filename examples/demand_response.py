"""Reduce datacenter demand after observing grid carbon intensity.

python examples/demand_response.py

This illustrative model changes demand at the next actor sample. It does not
model job deadlines, deferred work, or the energy needed to finish that work.
"""

import vessim as vs


class DemandResponse(vs.Controller):
    def __init__(self, datacenter):
        self.datacenter = datacenter

    def step(self, now, states):
        carbon = states["site"]["grid_signals"]["carbon"]
        self.datacenter.power = 700 if carbon > 0.3 else 1000


def main():
    datacenter = vs.Consumer("datacenter", power=1000)
    with vs.Environment("2026-01-01", step_size=60) as env:
        env.add_microgrid(
            name="site",
            actors=[datacenter],
            dispatchables=[vs.GridConnection()],
            grid_signals={"carbon": 0.4},  # kgCO2e/kWh
        )
        env.add_controller(DemandResponse(datacenter))
        recorder = env.add_controller(vs.Recorder())
        env.run(180)

    for now, states in recorder.log.items():
        demand = -states["site"]["actor_states"]["datacenter"]["power"]
        print(f"{now:%H:%M:%S}: {demand:.0f} W")


if __name__ == "__main__":
    main()
