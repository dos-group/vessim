from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional

from loguru import logger


class Storage(ABC):
    @abstractmethod
    def update(self, power: float, duration: int) -> float:
        """Feed or draw energy for specified duration.

        Args:
            power: Power to be (dis)charged in W. Charging if positive, discharging if negative.
            duration: Duration in seconds for which the storage will be (dis)charged.

        Returns:
            The total energy in Ws that has been charged/discharged.
        """

    def state(self) -> dict:
        """Returns information about the current state of the storage. Should be overridden."""
        return {}


class SimpleBattery(Storage):
    """(Way too) simple battery.

    Args:
        capacity: Battery capacity in watt-seconds (Ws).
        charge_level: Initial charge level in watt-seconds (Ws). Defaults to 0Ws.
        min_soc: Minimum allowed state of charge (SoC) for the battery.
            Defaults to 0%. Can be altered during simulation.
        c_rate: Optional C-rate, which defines the charge and discharge rate of the battery.
            For more information on C-rate, see `C-rate explanation <https://www.batterydesign.net/electrical/c-rate/>`_.
            Defaults to None.
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

        assert self.min_soc <= self.soc(), "Minimum SoC can not be smaller than the current SoC"
        if self.c_rate is not None:
            max_power = self.c_rate * self.capacity / 3600
            if power >= max_power:
                # Too high charge rate
                logger.info(
                    f"Trying to charge storage '{self.__class__.__name__}' with "
                    f"{power} W but only {max_power} W are supported."
                )
                power = max_power

            if power <= -max_power:
                # Too high discharge rate
                logger.info(
                    f"Trying to discharge storage '{self.__class__.__name__}' "
                    f"with {power} W but only {max_power} W are supported."
                )
                power = -max_power

        charged_energy = power * duration  # Total energy to be (dis)charged in Ws
        new_charge_level = self.charge_level + charged_energy

        abs_min_soc = self.min_soc * self.capacity
        if new_charge_level < abs_min_soc:
            # Battery can not be discharged further than the minimum state-of-charge
            charged_energy = abs_min_soc - self.charge_level
            self.charge_level = abs_min_soc
        elif new_charge_level > self.capacity:
            # Battery can not be charged past its capacity
            charged_energy = self.capacity - self.charge_level
            self.charge_level = self.capacity
        else:
            self.charge_level = new_charge_level

        return charged_energy

    def soc(self) -> float:
        return self.charge_level / self.capacity

    def state(self) -> dict:
        return {
            "soc": self.soc(),
            "charge_level": self.charge_level,
            "capacity": self.capacity,
            "min_soc": self.min_soc,
            "c_rate": self.c_rate,
        }
