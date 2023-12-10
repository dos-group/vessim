from typing import Dict

from vessim.core.microgrid import Microgrid as _Microgrid
from vessim.cosim._util import SimWrapper, VessimSimulator, VessimModel


class Microgrid(SimWrapper):
    def __init__(self, microgrid: _Microgrid) -> None:
        sim_name = type(self).__name__
        factory_name = sim_name + "Sim"
        super().__init__(factory_name, sim_name)
        self.microgrid = microgrid

    def _factory_args(self):
        return (self.sim_name,), {}

    def _sim_args(self):
        return (), {"microgrid": self.microgrid}


class MicrogridSim(VessimSimulator):

    META = {
        "type": "event-based",
        "models": {
            "Microgrid": {
                "public": True,
                "params": ["microgrid"],
                "attrs": ["p", "p_delta"],
            },
        },
    }

    def __init__(self) -> None:
        self.step_size = None
        super().__init__(self.META, _MicrogridModel)

    def next_step(self, time):
        return None


class _MicrogridModel(VessimModel):
    def __init__(self, microgrid: _Microgrid):
        self.microgrid = microgrid
        self.p_delta = 0.0
        self._last_step_time = 0

    def step(self, time: int, inputs: Dict) -> None:
        duration = time - self._last_step_time
        if duration > 0:
            self.p_delta = self.microgrid.power_flow(p=inputs["p"], duration=duration)
        self._last_step_time = time
