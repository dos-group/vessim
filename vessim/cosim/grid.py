from typing import Dict, Optional

from vessim.core.storage import Storage, StoragePolicy, DefaultStoragePolicy
from vessim.cosim._util import VessimSimulator, VessimModel


class GridSim(VessimSimulator):

    META = {
        "type": "event-based",
        "models": {
            "Grid": {
                "public": True,
                "params": ["storage", "policy"],
                "attrs": ["p", "p_delta"],
            },
        },
    }

    def __init__(self) -> None:
        self.step_size = None
        super().__init__(self.META, _GridModel)

    def next_step(self, time):
        return None


class _GridModel(VessimModel):
    def __init__(
        self,
        storage: Optional[Storage] = None,
        policy: Optional[StoragePolicy] = None
    ):
        self.storage = storage
        self.policy = policy if policy is not None else DefaultStoragePolicy()

        self.p_delta = 0.0
        self._last_step_time = 0

    def step(self, time: int, inputs: Dict) -> None:
        duration = time - self._last_step_time
        self._last_step_time = time

        if duration == 0:
            return

        p_delta = sum(inputs["p"].values())
        if self.storage is None:
            self.p_delta = p_delta
        else:
            self.p_delta = self.policy.apply(self.storage, p_delta, duration)
