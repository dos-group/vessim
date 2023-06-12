from datetime import datetime

from vessim._util import Time, TraceSimulator, Clock
from vessim.core import VessimSimulator, VessimModel


class Generator(TraceSimulator):

    def power_at(self, dt: Time):
        try:
            return self.data.loc[self.data.index.asof(dt)]
        except KeyError:
            raise ValueError(f"Cannot retrieve power at {dt}.")


class GeneratorSim(VessimSimulator):

    META = {
        'type': 'time-based',
        'models': {
            'Generator': {
                'public': True,
                'params': [
                    'generator'
                ],
                'attrs': [
                    'p',
                ],
            },
        },
    }

    def __init__(self):
        super().__init__(self.META, GeneratorModel)

    def init(self, sid, time_resolution, sim_start: datetime, generator: Generator,
             eid_prefix=None):
        super().init(sid, time_resolution, eid_prefix=eid_prefix)
        self.clock = Clock(sim_start)
        self.generator = generator
        return self.meta

    def create(self, num, model):
        return super().create(num, model, generator=self.generator, clock=self.clock)

    def next_step(self, time: int) -> int:
        dt = self.clock.to_datetime(time)
        next_dt = self.generator.next_update(dt)
        return self.clock.to_simtime(next_dt)


class GeneratorModel(VessimModel):
    def __init__(self, generator: Generator, clock: Clock):
        self.generator = generator
        self.clock = clock
        self.p = None

    def step(self, time: int, inputs: dict) -> None:
        dt = self.clock.to_datetime(time)
        self.p = self.generator.power_at(dt)
