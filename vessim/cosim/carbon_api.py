from datetime import datetime

from vessim import TimeSeriesApi
from vessim.cosim._util import SimWrapper, VessimSimulator, VessimModel, Clock


class CarbonApi(SimWrapper):
    def __init__(self, carbon_api: TimeSeriesApi, zone: str) -> None:
        sim_name = type(self).__name__
        factory_name = sim_name + "Sim"
        super().__init__(factory_name, sim_name)
        self.carbon_api = carbon_api
        self.zone = zone

    def _factory_args(self):
        return (self.sim_name,), {
            "sim_start": self.cosim_data.sim_start,
            "carbon_api": self.carbon_api
        }

    def _sim_args(self):
        return (), {"zone": self.zone}


class CarbonApiSim(VessimSimulator):

    META = {
        'type': 'time-based',
        'models': {
            'CarbonApi': {
                'public': True,
                'params': ['zone'],
                'attrs': ['carbon_intensity'],
            },
        },
    }

    def __init__(self):
        super().__init__(self.META, _CarbonApiModel)
        self.clock = None
        self.sim_start = None
        self.carbon_api = None

    def init(self, sid, time_resolution, sim_start: datetime, # type: ignore
            carbon_api: TimeSeriesApi, eid_prefix=None):
        super().init(sid, time_resolution, eid_prefix=eid_prefix)
        self.clock = Clock(sim_start)
        self.carbon_api = carbon_api
        return self.meta

    def create(self, num, model, *args, **kwargs):
        return super().create(num, model, *args, **kwargs, clock=self.clock,
                              carbon_api=self.carbon_api)

    def next_step(self, time: int) -> int:
        dt = self.clock.to_datetime(time)
        next_dt = self.carbon_api.next_update(dt)
        return self.clock.to_simtime(next_dt)


class _CarbonApiModel(VessimModel):
    def __init__(self, carbon_api: TimeSeriesApi, clock: Clock, zone: str):
        self.api = carbon_api
        self.clock = clock
        self.zone = zone
        self.carbon_intensity = 0.0

    def step(self, time: int, inputs: dict) -> None:
        dt = self.clock.to_datetime(time)
        self.carbon_intensity = self.api.actual(dt, self.zone)
