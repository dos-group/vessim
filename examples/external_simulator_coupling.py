"""Couple an independent simulator to a Vessim microgrid in either mode.

Install vessim[mosaik], then run:
    python examples/external_simulator_coupling.py
    python examples/external_simulator_coupling.py --live
"""

from __future__ import annotations

import argparse

import mosaik_api_v3
import vessim as vs


class LoadSimulator(mosaik_api_v3.Simulator):
    def __init__(self):
        super().__init__(
            {
                "type": "time-based",
                "models": {
                    "Load": {"public": True, "params": [], "attrs": ["power"]},
                },
            }
        )
        self.power = 0

    def init(self, sid, time_resolution=1.0, **params):
        return self.meta

    def create(self, num, model):
        return [{"eid": str(i), "type": model} for i in range(num)]

    def step(self, time, inputs, max_advance):
        self.power = -100 - 10 * time
        return time + 1

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
        sim_config={
            "Load": {"python": "external_simulator_coupling:LoadSimulator"},
        },
    ) as env:
        load = env.world.start("Load").Load()
        env.add_microgrid(actors=[], name="site", dispatchables=[vs.GridConnection()])
        recorder = env.add_controller(vs.Recorder(timeseries=False))
        env.prepare()
        env.world.connect(load, env.entities["site"], "power")
        result = env.run(until=3)
        print(result.states["site"])
        print(recorder.result.metrics)


if __name__ == "__main__":
    main()
