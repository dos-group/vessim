from collections import defaultdict
from datetime import datetime
from typing import Dict, Callable, Any

import pandas as pd

from vessim.cosim._util import Clock, VessimSimulator, VessimModel, simplify_inputs


class MonitorSim(VessimSimulator):

    META = {
        "type": "time-based",
        "models": {
            "Monitor": {
                "public": True,
                "any_inputs": True,
                "params": ["out_path", "fn"],
                "attrs": [],
            },
        },
    }

    def __init__(self) -> None:
        """Simple data collector for printing data at the end of simulation."""
        self.step_size = None
        self.clock = None
        super().__init__(self.META, _MonitorModel)

    def init(self, sid, time_resolution, sim_start: datetime,  # type: ignore
             step_size: int, eid_prefix=None):
        self.step_size = step_size  # type: ignore
        self.clock = Clock(sim_start)  # type: ignore
        return super().init(sid, time_resolution, eid_prefix=eid_prefix)

    def create(self, num, model, *args, **kwargs):  # type: ignore
        return super().create(num, model, *args, **kwargs, clock=self.clock)

    def finalize(self):
        """Collected data is printed to file at simulation end."""
        for model in self.entities.values():
            model: _MonitorModel
            model.finalize()

    def next_step(self, time):
        return time + self.step_size


class _MonitorModel(VessimModel):
    def __init__(self, out_path: str, fn: Callable[[], Dict[str, Any]], clock: Clock):
        self.out_path = out_path
        self.fn = fn
        self._clock = clock
        self.data: Dict = defaultdict(dict)

    def step(self, time: int, inputs: Dict) -> None:
        inputs = simplify_inputs(inputs)
        dt = self._clock.to_datetime(time)
        # TODO Reimplement logging on DEBUG level
        # logger.info(f"# --- {str(dt):>5} ---")

        if self.fn is not None:
            inputs.update(self.fn())

        for attr, value in inputs.items():
            # logger.info(f"{attr}: {value}")
            self.data[attr][dt] = value

    def finalize(self):
        """Collected data is printed to file at simulation end."""
        pd.DataFrame(self.data).to_csv(self.out_path)
