from datetime import datetime
from typing import Optional

from vessim import TimeSeriesApi
from vessim.cosim._util import SimWrapper, Clock, VessimSimulator, VessimModel


class Generator(SimWrapper):
    def __init__(self, generator: TimeSeriesApi) -> None:
        sim_name = type(self).__name__
        factory_name = sim_name + "Sim"
        super().__init__(factory_name, sim_name)
        self.generator = generator

    def _factory_args(self):
        return (self.sim_name,), {"sim_start": self.cosim_data.sim_start}

    def _sim_args(self):
        return (), {"generator": self.generator}


class GeneratorSim(VessimSimulator):

    META = {
        "type": "time-based",
        "models": {
            "Generator": {
                "public": True,
                "params": ["generator"],
                "attrs": ["p"],
            },
        },
    }

    def __init__(self):
        super().__init__(self.META, _GeneratorModel)

    def init(self, sid, time_resolution, sim_start: datetime,  # type: ignore
             eid_prefix=None):
        super().init(sid, time_resolution, eid_prefix=eid_prefix)
        self.clock = Clock(sim_start)
        return self.meta

    def create(self, num, model, *args, **kwargs):
        return super().create(num, model, *args, **kwargs, clock=self.clock)

    def next_step(self, time: int) -> int:
        dt = self.clock.to_datetime(time)
        next_dt = min(e.generator.next_update(dt)   # type: ignore
                      for e in self.entities.values())
        return self.clock.to_simtime(next_dt)


class _GeneratorModel(VessimModel):
    def __init__(self, generator: TimeSeriesApi, clock: Clock):
        self.generator = generator
        self.clock = clock
        self.p: Optional[float] = None

    def step(self, time: int, inputs: dict) -> None:
        dt = self.clock.to_datetime(time)
        self.p = self.generator.actual(dt)
