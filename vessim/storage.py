from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, Any

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

    @abstractmethod
    def soc(self) -> float:
        """Returns the state-of-charge (SoC) of the battery.

        Values should range between 0 (empty) and 1 (full).
        """

    def set_parameter(self, key: str, value: Any) -> None:
        """Fuction to let a controller update a storage parameter during a simulation using Mosaik.

        In the default case, the attribute with the name of the key is set on the storage object.
        The function can be subclassed to allow other ways of setting parameters.
        """
        if not hasattr(self, key):
            logger.warning(f"Attribute {key} of storage was never previously set.")
        setattr(self, key, value)

    def state(self) -> dict:
        """Returns information about the current state of the storage. Should be overridden."""
        return {}


class SimpleBattery(Storage):
    """(Way too) simple battery.

    Args:
        capacity: Battery's energy capacity. (Wh).
        initial_soc: Initial battery state-of-charge. Has to be between 0 and 1. Defaults to 0.
        min_soc: Minimum allowed state of charge (SoC) for the battery. Has to be between 0 and 1.
            Defaults to 0. Can be altered during simulation.
        c_rate: Optional C-rate, which defines the charge and discharge rate of the battery.
            For more information on C-rate, see `C-rate explanation <https://www.batterydesign.net/electrical/c-rate/>`_.
            Defaults to None.
    """

    def __init__(
        self,
        capacity: float,
        initial_soc: float = 0,
        min_soc: float = 0,
        c_rate: Optional[float] = None,
    ):
        self.capacity = capacity
        assert 0 <= initial_soc <= 1
        self.charge_level = capacity * initial_soc
        self._soc = initial_soc
        assert 0 <= min_soc <= self._soc
        self.min_soc = min_soc
        self.c_rate = c_rate

    def update(self, power: float, duration: int) -> float:
        """Charges the battery with specific power for a duration.

        Updates batteries energy level according to power that is fed to/ drawn from the battery.
        Battery won't be charged further than the capacity and won't be discharged further than the
        minimum state-of-charge.
        Batteries charging/ discharging rate is limited be the c_rate (if set).
        """
        if duration <= 0.0:
            raise ValueError("Duration needs to be a positive value")

        assert self.min_soc <= self._soc, "Minimum SoC can not be smaller than the current SoC"
        if self.c_rate is not None:
            max_power = self.c_rate * self.capacity
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

        charged_energy = power * duration
        new_charge_level = self.charge_level + charged_energy / 3600

        abs_min_soc = self.min_soc * self.capacity
        if new_charge_level < abs_min_soc:
            # Battery can not be discharged further than the minimum state-of-charge
            charged_energy = (abs_min_soc - self.charge_level) * 3600
            self.charge_level = abs_min_soc
            self._soc = self.min_soc
        elif new_charge_level > self.capacity:
            # Battery can not be charged past its capacity
            charged_energy = (self.capacity - self.charge_level) * 3600
            self.charge_level = self.capacity
            self._soc = 1.0
        else:
            self.charge_level = new_charge_level
            self._soc = self.charge_level / self.capacity

        return charged_energy

    def soc(self) -> float:
        return self._soc

    def state(self) -> dict:
        """Returns state information of the battery as a dict."""
        return {
            "soc": self._soc,
            "charge_level": self.charge_level,
            "capacity": self.capacity,
            "min_soc": self.min_soc,
            "c_rate": self.c_rate,
        }
