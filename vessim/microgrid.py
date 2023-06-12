from abc import ABC, abstractmethod
from typing import Optional, Callable, Union

from vessim.core import VessimSimulator, VessimModel
from vessim.storage import Storage, StoragePolicy, DefaultStoragePolicy


class MicrogridSim(VessimSimulator):

    META = {
        "type": "event-based",
        "models": {
            "Microgrid": {
                "public": True,
                "params": ["storage", "policy"],
                "attrs": ["p", "p_delta"],
            },
        },
    }

    def __init__(self) -> None:
        self.step_size = None
        super().__init__(self.META, MicrogridModel)

    def next_step(self, time):
        return None


class MicrogridModel(VessimModel):
    def __init__(self,
                 storage: Optional[Storage] = None,
                 policy: Optional[StoragePolicy] = None):
        self.storage = storage
        self.policy = policy if policy is not None else DefaultStoragePolicy()
        self.p_delta = 0.0
        self._last_step_time = 0

    def step(self, time: int, inputs: dict) -> None:
        p: Union[float, list[float]] = inputs["p"]
        p_delta = p if type(p) == float else sum(inputs["p"])
        time_since_last_step = time - self._last_step_time
        if self.storage is None:
            self.p_delta = p_delta
        else:
            self.p_delta = self.policy.apply(self.storage, p_delta, time_since_last_step)
        self._last_step_time = time
