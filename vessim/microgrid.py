from abc import ABC, abstractmethod
from typing import Optional, Callable

from vessim.core import VessimSimulator, VessimModel
from vessim.storage import Storage, StoragePolicy, DefaultStoragePolicy


class MicrogridSim(VessimSimulator):

    META = {
        "type": "event-based",
        "models": {
            "MicrogridModel": {
                "public": True,
                "params": ["storage", "policy"],
                "attrs": ["p_gen", "p_cons", "p_grid"],
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
        self.p_gen = 0.0
        self.p_cons = 0.0
        self.p_grid = 0.0
        self._last_step_time = 0

    def step(self, time: int, inputs: dict) -> None:
        self.p_gen = inputs["p_gen"]
        self.p_cons = inputs["p_cons"]
        p_delta = self.p_gen - self.p_cons
        time_since_last_step = time - self._last_step_time
        if self.storage is None:
            self.p_grid = p_delta
        else:
            self.p_grid = self.policy.apply(self.storage, p_delta, time_since_last_step)
        self._last_step_time = time
