from collections import defaultdict
from datetime import datetime
from typing import Dict, Callable, Any, Optional

import pandas as pd

from vessim.cosim._util import Clock, VessimSimulator, VessimModel, simplify_inputs


class Ecovisor:

    def __init__(
        self,
        monitor_fn: Optional[Callable[[], Dict[str, Any]]] = None,
    ):
        self.data: Dict = defaultdict(dict)
        self.monitor_fn = monitor_fn
        self._clock = None

    def initialize(self, sim_start: datetime):
        self._clock = Clock(sim_start)

    def step(self, time: int, inputs: Dict) -> None:
        self._monitor(time, inputs)
        # TODO other tasks like hosting a REST server and adapting the simulation

    def _monitor(self, time: int, inputs: Dict):
        inputs = simplify_inputs(inputs)
        dt = self._clock.to_datetime(time)

        if self.monitor_fn is not None:
            inputs.update(self.monitor_fn())

        for attr, value in inputs.items():
            self.data[attr][dt] = value

    def monitor_to_csv(self, out_path: str):
        pd.DataFrame(self.data).to_csv(out_path)


class EcovisorSim(VessimSimulator):

    META = {
        "type": "time-based",
        "models": {
            "Ecovisor": {
                "public": True,
                "any_inputs": True,
                "params": ["ecovisor"],
                "attrs": [],
            },
        },
    }

    def __init__(self) -> None:
        """Simple data collector for printing data at the end of simulation."""
        self.step_size = None
        super().__init__(self.META, _EcovisorModel)

    def init(self, sid, time_resolution, step_size: int, eid_prefix=None):
        self.step_size = step_size  # type: ignore
        return super().init(sid, time_resolution, eid_prefix=eid_prefix)

    def next_step(self, time):
        return time + self.step_size


class _EcovisorModel(VessimModel):
    def __init__(self, ecovisor: Ecovisor):
        self.ecovisor = ecovisor

    def step(self, time: int, inputs: Dict) -> None:
        self.ecovisor.step(time, inputs)
        # TODO here we need to set all properties that other entities should
        #   have access to in the simulation (if there are any)
