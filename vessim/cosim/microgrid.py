from typing import Dict

from vessim.core.microgrid import Microgrid
from vessim.cosim._util import VessimSimulator, VessimModel


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
    def __init__(self, microgrid: Microgrid):
        self.microgrid = microgrid
        self.p_delta = 0.0
        self._last_step_time = 0

    def step(self, time: int, inputs: Dict) -> None:
        duration = time - self._last_step_time
        if duration > 0:
            self.p_delta = self.microgrid.power_flow(p=inputs["p"], duration=duration)
        self._last_step_time = time
