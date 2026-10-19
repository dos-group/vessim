"""Respond to a temporary import limit under a flexible connection agreement.

python examples/demand_response.py

Limits are announced one simulation step before they take effect. The toy
simulator adjusts concurrent jobs, assuming enough flexible work is available.
It does not model job completion, deadlines, or the cost of pausing work.
"""

import pandas as pd

import argparse
from pathlib import Path
from _common import fresh_output

import vessim as vs


class DatacenterSimulator:
    """Model a 400 W base load and up to six concurrent 100 W jobs."""

    def __init__(self):
        self.active_jobs = 6

    def set_power_budget(self, watts):
        if watts < 400:
            raise ValueError("The power budget cannot cover the base load.")
        self.active_jobs = min(6, int((watts - 400) // 100))

    def power(self):
        return 400 + 100 * self.active_jobs


class DatacenterPower(vs.Signal):
    def __init__(self, datacenter):
        self.datacenter = datacenter

    def at(self, elapsed=None):
        return self.datacenter.power()


class DemandResponse(vs.Controller):
    def __init__(self, datacenter, grid):
        self.datacenter = datacenter
        self.grid = grid

    def step(self, now, states):
        limit = states["site"]["grid_signals"]["next_import_limit"]
        self.datacenter.set_power_budget(limit)
        self.grid.max_import = limit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("results/demand_response"))
    args = parser.parse_args()
    fresh_output(args.output)
    datacenter = DatacenterSimulator()
    grid = vs.GridConnection(max_import=1000)
    notices = vs.Trace(pd.Series([700, 700, 1000, 1000], index=[0, 60, 120, 180]))
    with vs.Environment("2026-01-01", step_size=60) as env:
        env.add_microgrid(
            name="site",
            actors=[vs.Consumer("datacenter", signal=DatacenterPower(datacenter))],
            dispatchables=[grid],
            grid_signals={"next_import_limit": notices},
        )
        env.add_controller(DemandResponse(datacenter, grid))
        recorder = env.add_controller(vs.Recorder(args.output, run_id="demand-response"))
        env.run(240)

    for (now, _), row in recorder.to_df().iterrows():
        demand = -row["actor_states.datacenter.power"]
        print(f"{now:%H:%M:%S}: {demand:.0f} W")


if __name__ == "__main__":
    main()
