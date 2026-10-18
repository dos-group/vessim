"""Connect a small datacenter load simulator to a Vessim microgrid.

Install vessim[mosaik], then run:
    python examples/external_simulator_coupling.py
    python examples/external_simulator_coupling.py --live
"""

from __future__ import annotations

import argparse

import mosaik_api_v3
import vessim as vs


class DatacenterSimulator(mosaik_api_v3.Simulator):
    def __init__(self):
        super().__init__(
            {
                "type": "time-based",
                "models": {
                    "Datacenter": {"public": True, "params": [], "attrs": ["power"]},
                },
            }
        )
        self.power = 0

    def init(self, sid, time_resolution=1.0, **params):
        return self.meta

    def create(self, num, model):
        return [{"eid": str(i), "type": model} for i in range(num)]

    def step(self, time, inputs, max_advance):
        # More jobs arrive each minute, increasing demand from 1 kW to 2 kW.
        self.power = -(1000 + 500 * (time // 60))
        return time + 60

    def get_data(self, outputs):
        return {eid: {"power": self.power} for eid in outputs}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    create = vs.Environment.live if args.live else vs.Environment
    with create(
        sim_start="2026-01-01",
        backend="mosaik",
        step_size=60,
        sim_config={
            "Datacenter": {"python": "external_simulator_coupling:DatacenterSimulator"},
        },
    ) as env:
        datacenter = env.world.start("Datacenter").Datacenter()
        env.add_microgrid(actors=[], name="site", dispatchables=[vs.GridConnection()])
        recorder = env.add_controller(vs.Recorder(timeseries=False))
        env.prepare()
        env.world.connect(datacenter, env.entities["site"], "power")
        result = env.run(until=180)
        print(result.states["site"])
        print(recorder.result.metrics)


if __name__ == "__main__":
    main()
