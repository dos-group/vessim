from abc import ABC, abstractmethod
from typing import Optional

from loguru import logger


class Storage(ABC):

    @abstractmethod
    def update(self, power: float, duration: int) -> float:
        """Feed or draw energy for specified duration.

        Args:
            power: Charging if positive, discharging if negative.
            duration: Duration in seconds for which the storage will be (dis)charged.

        Returns:
            The power delta, in case not all requested power could be discharged from or
            charged into the battery. This can happen either if the batter is full/empty
            or if the C-rate was exceeded.
            If 0, all power was successfully (dis)charged.
        """


class SimpleBattery(Storage):
    """(Way too) simple battery.

    Args:
        capacity: Battery capacity in Ws
        charge_level: Initial charge level in Ws
        min_soc: Minimum allowed soc for the battery
        c_rate: C-rate (https://www.batterydesign.net/electrical/c-rate/)
    """

    def __init__(self,
                 capacity: float,
                 charge_level: float = 0,
                 min_soc: float = 0,
                 c_rate: Optional[float] = None):
        self.capacity = capacity
        assert 0 <= charge_level <= self.capacity
        self.charge_level = charge_level
        assert 0 <= min_soc <= self.soc()
        self.min_soc = min_soc
        self.c_rate = c_rate

    def update(self, power: float, duration: int) -> float:
        max_charge_p_delta, p_delta = 0, 0

        if self.c_rate is not None:
            max_rate = self.c_rate * self.capacity / 3600
            if power >= max_rate:
                logger.info(f"Trying to charge storage '{__class__.__name__}' with "
                            f"{power} W but only {max_rate} W are supported.")
                max_charge_p_delta = power - max_rate
                power = max_rate

            if power <= -max_rate:
                logger.info(f"Trying to discharge storage '{__class__.__name__}' with "
                            f"{power} W but only {max_rate} W are supported.")
                max_charge_p_delta = power + max_rate
                power = -self.c_rate

        charge_energy = power * duration
        new_charge_level = self.charge_level + power * duration

        abs_min_soc = self.min_soc * self.capacity
        if new_charge_level < abs_min_soc:
            p_delta = (new_charge_level - abs_min_soc) / duration
            self.charge_level = abs_min_soc
        elif new_charge_level > self.capacity:
            p_delta = (new_charge_level - self.capacity) / duration
            self.charge_level = self.capacity
        else:
            self.charge_level += charge_energy

        return p_delta + max_charge_p_delta

    def soc(self):
        return self.charge_level / self.capacity


class StoragePolicy(ABC):

    @abstractmethod
    def apply(self, storage: Storage, p_delta: float, time_since_last_step: int) -> float:
        """(Dis)charge the storage according to the policy."""


class DefaultStoragePolicy(StoragePolicy):

    def __init__(self, grid_power: float = 0):
        """Storage policy which tries to (dis)charge as much of the delta as possible.

        Args:
            grid_power: If not 0, the battery is in "charge mode" and will draw the
                provided power from the grid. In this case, the delta simply returned
                together with the demand for charging.
        """
        self.grid_power = grid_power

    def apply(self, storage: Storage, p_delta: float, time_since_last_step: int) -> float:
        if self.grid_power == 0:
            return storage.update(power=p_delta, duration=time_since_last_step)
        else:
            excess_energy = storage.update(power=self.grid_power,
                                           duration=time_since_last_step)
            real_charge_power = self.grid_power - excess_energy / time_since_last_step
            return p_delta - real_charge_power