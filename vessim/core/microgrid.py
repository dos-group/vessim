from abc import ABC, abstractmethod
from typing import Dict, Optional

from vessim.core.storage import Storage, StoragePolicy, DefaultStoragePolicy


class Microgrid(ABC):
    @abstractmethod
    def power_flow(self, p: Dict[str, float], duration: int) -> float:
        """Calculates the microgrids power flow.

        Args:
            p: Maps power consumers/producers to the amount of power they demand/supply
            duration: Duration of the power flow (relevant for battery (dis)charge)

        Returns:
            Power delta (excess power if positive, power demand if negative)
        """


class SimpleMicrogrid(Microgrid):
    def __init__(
        self, storage: Optional[Storage] = None, policy: Optional[StoragePolicy] = None
    ):
        """Simply aggregates all supplied and demanded power.

        Args:
            storage: Optional energy storage to be used to (dis)charge a power delta
            policy: Storage policy on when and how to use the battery
        """
        self.storage = storage
        self.policy = policy if policy is not None else DefaultStoragePolicy()

    def power_flow(self, p: Dict[str, float], duration: int) -> float:
        p_delta = sum(p.values())
        if self.storage is None:
            return p_delta
        else:
            return self.policy.apply(self.storage, p_delta, duration)
