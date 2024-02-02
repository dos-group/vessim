from __future__ import annotations

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

    @abstractmethod
    def soc(self) -> float:
        """Returns the current State of Charge (SoC)."""

    @abstractmethod
    def state(self) -> dict:
        """Returns information about the current state of the storage."""


class SimpleBattery(Storage):
    """(Way too) simple battery.

    Args:
        capacity: Battery capacity in watt-hours (Wh).
        charge_level: Initial charge level in watt-hours (Wh).
        min_soc: Minimum allowed state of charge (SoC) for the battery.
        c_rate: C-rate, which defines the charge and discharge rate of the battery.
            For more information on C-rate, see `C-rate explanation <https://www.batterydesign.net/electrical/c-rate/>`_.
    """

    def __init__(
        self,
        capacity: float,
        charge_level: float = 0,
        min_soc: float = 0,
        c_rate: Optional[float] = None,
    ):
        self.capacity = capacity
        assert 0 <= charge_level <= self.capacity
        self.charge_level = charge_level
        assert 0 <= min_soc <= self.soc()
        self.min_soc = min_soc
        self.c_rate = c_rate

    def update(self, power: float, duration: int) -> float:
        if duration <= 0.0:
            raise ValueError("Duration needs to be a positive value")

        max_charge_p_delta, p_delta = 0.0, 0.0

        if self.c_rate is not None:
            max_rate = self.c_rate * self.capacity / 3600
            if power >= max_rate:
                logger.info(
                    f"Trying to charge storage '{self.__class__.__name__}' with "
                    f"{power} W but only {max_rate} W are supported."
                )
                max_charge_p_delta = power - max_rate
                power = max_rate

            if power <= -max_rate:
                logger.info(
                    f"Trying to discharge storage '{self.__class__.__name__}' "
                    f"with {power} W but only {max_rate} W are supported."
                )
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

    def soc(self) -> float:
        return self.charge_level / self.capacity

    def state(self) -> dict:
        return {
            "charge_level": self.charge_level,
            "capacity": self.capacity,
            "min_soc": self.min_soc,
            "c_rate": self.c_rate,
        }


class StoragePolicy(ABC):
    @abstractmethod
    def apply(self, storage: Storage, p_delta: float, time_since_last_step: int) -> float:
        """(Dis)charge the storage according to the policy."""

    @abstractmethod
    def state(self) -> dict:
        """Returns information about the current state of the storage policy."""


class DefaultStoragePolicy(StoragePolicy):
    """Storage policy which tries to (dis)charge as much of the delta as possible.

    Args:
        grid_power: If not 0, the battery is in "charge mode" and will draw the
            provided power from the grid. In this case, the delta simply returned
            together with the demand for charging.
    """

    def __init__(self, grid_power: float = 0):
        self.grid_power = grid_power

    def apply(self, storage: Storage, p_delta: float, time_since_last_step: int) -> float:
        if self.grid_power == 0:
            return storage.update(power=p_delta, duration=time_since_last_step)
        else:
            excess_energy = storage.update(
                power=self.grid_power, duration=time_since_last_step
            )
            real_charge_power = self.grid_power - excess_energy
            return p_delta - real_charge_power

    def state(self) -> dict:
        return {
            "grid_power": self.grid_power,
        }
