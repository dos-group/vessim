from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, Any

import numpy as np
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
        initial_soc: Initial battery state-of-charge (SoC). Has to be between 0 and 1.
            Defaults to 0.
        min_soc: Minimum allowed SoC for the battery. Has to be between 0 and 1.
            If current SoC is below or equal to the minimum SoC, battery is not discharged further.
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
        assert 0 <= initial_soc <= 1, "Invalid initial state-of-charge. Has to be between 0 and 1."
        self.charge_level = capacity * initial_soc
        self._soc = initial_soc
        assert 0 <= min_soc <= 1, "Invalid minimum state-of-charge. Has to be between 0 and 1."
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

        if self._soc <= self.min_soc and power <= 0.0:
            return 0.0

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


class ClcBattery(Storage):
    """Implementation of the C-L-C Battery model for lithium-ion batteries.

    This class implements the C-L-C model as described in:
        Kazhamiaka, F., Rosenberg, C. & Keshav, S.
        Tractable lithium-ion storage models for optimizing energy systems.
        Energy Inform 2, 4 (2019). https://doi.org/10.1186/s42162-019-0070-6

    The default parameterization models a pack of LGM50 21700 rechargable lithium-ion cells.
    This model should not be used in combination with large step sizes.

    Args:
        number_of_cells: Number of cells in the battery pack. Defaults to 1.
        initial_soc: Initial battery state-of-charge (SoC). Has to be between 0 and 1.
            Defaults to 0.
        min_soc: Minimum allowed SoC for the battery. Has to be between 0 and 1.
            If current SoC is below or equal to the minimum SoC, battery is not discharged further.
            Defaults to 0. Can be altered during simulation.
        nom_voltage: Single cell nominal voltage in V. Defaults to 3.63V.
        u_1: Linear factor for lower energy limit of cell depending on applied discharge current.
            Defaults to -0.087Wh/A.
        v_1: Offset for lower energy limit of cell depending on the applied discharge current.
            Defaults to 0.0Wh.
        u_2: Linear factor for upper energy limit of cell depending on the applied charge current.
            Defaults to -1.326Wh/A.
        v_2: Offset for upper energy limit of cell depending on the applied charge current. This
            parameter can be viewed as the capacity of a single cell. Defaults to 19.14Wh.
        alpha_d: Maximum discharging C-rate. Defaults to -1.5C.
        alpha_c: Maximum charging C-rate. Defaults to 0.7C.
        eta_d: Average fraction of power that has to be discharged from cell to obtain said
            power. Is equivalent to the discharging inefficiency. Should be greater or equal to 1.
            Defaults to 1.014.
        eta_c: Average fraction of power that is stored in cell when charged at said power.
            Is equivalent to the charging inefficiency. Should be between 0 and 1.
            Defaults to 0.978.
        discharging_current_cutoff: If the maximum allowed discharging current is higher than this
            value, discharging is stopped. Mainly serves to avoid numerical issues when
            discharging at a very low SoC. Defaults to -0.05A.
        charging_current_cutoff: If the maximum allowed charging current is lower than this value,
            charging is stopped. Mainly serves to avoid numerical issues when charging at a very
            high SoC. Defaults to 0.05A.
    """

    def __init__(
        self,
        number_of_cells: int = 1,
        initial_soc: float = 0,
        min_soc: float = 0,
        nom_voltage: float = 3.63,
        u_1: float = -0.087,
        v_1: float = 0.0,
        u_2: float = -1.326,
        v_2: float = 19.14,
        alpha_d: float = -1.5,
        alpha_c: float = 0.7,
        eta_d: float = 1.014,
        eta_c: float = 0.978,
        discharging_current_cutoff: float = -0.05,
        charging_current_cutoff: float = 0.05,
    ) -> None:
        assert number_of_cells > 0, "There has to be a positive number of cells."
        self.number_of_cells = number_of_cells
        self.u_1 = u_1
        self.v_1 = v_1
        self.u_2 = u_2
        self.v_2 = v_2
        assert 0 <= initial_soc <= 1, "Invalid initial state-of-charge. Has to be between 0 and 1."
        self._soc = initial_soc
        self.charge_level = self.v_2 * initial_soc # Charge level of one cell
        assert 0 <= min_soc <= 1, "Invalid minimum state-of-charge. Has to be between 0 and 1."
        self.min_soc = min_soc
        self.nom_voltage = nom_voltage
        self.alpha_d = alpha_d * self.v_2
        self.alpha_c = alpha_c * self.v_2
        assert eta_d >= 1, "Invalid discharging inefficiency. Has to be greater or equal to 1."
        self.eta_d = eta_d
        assert 0 <= eta_c <= 1, "Invalid charging inefficiency. Has to be between 0 and 1."
        self.eta_c = eta_c
        self.discharging_power_cutoff = discharging_current_cutoff * self.nom_voltage
        self.charging_power_cutoff = charging_current_cutoff * self.nom_voltage

    def soc(self) -> float:
        return self._soc

    def update(self, power: float, duration: int) -> float:
        if duration <= 0.0:
            raise ValueError("Duration needs to be a positive value")

        if power > 0:
            return self.charge(power, duration)
        elif power < 0 and self.soc() > self.min_soc:
            return self.discharge(power, duration)
        else:
            return 0

    def charge(self, power: float, duration: int) -> float:
        # Apply charging power limits
        max_power = (
            np.minimum(
                (self.charge_level - self.v_2)
                / (self.u_2 / self.nom_voltage - duration * self.eta_c / 3600),
                self.alpha_c,
            )
            * self.number_of_cells
        )
        if power > max_power:
            power = max_power if max_power >= self.charging_power_cutoff else 0.0

        # Update battery parameters
        self.charge_level += self.eta_c * (power / self.number_of_cells) * (duration / 3600)
        self._soc = self.charge_level / self.v_2
        return power * duration

    def discharge(self, power: float, duration: int) -> float:
        # Apply discharging power limits
        min_power = (
            np.maximum(
                (self.charge_level - self.v_1)
                / (self.u_1 / self.nom_voltage - duration * self.eta_d / 3600),
                self.alpha_d,
            )
            * self.number_of_cells
        )
        if power < min_power:
            power = min_power if min_power <= self.charging_power_cutoff else 0.0

        # Compute energy delta
        discharge_energy = self.eta_d * (power / self.number_of_cells) * (duration / 3600)

        # Determine if battery would be discharged past the min-soc
        if (self.charge_level + discharge_energy) < self.min_soc * self.v_2:
            limited_discharge_energy = (self.min_soc * self.v_2 - self.charge_level) / self.eta_d
            self.charge_level = self.v_2 * self.min_soc
            self._soc = self.min_soc
            return limited_discharge_energy * self.number_of_cells * 3600

        # Update battery parameters
        self.charge_level += discharge_energy
        self._soc = self.charge_level / self.v_2
        return power * duration

    def state(self) -> dict:
        return {
            "soc": self._soc,
            "charge_level": self.charge_level * self.number_of_cells,
            "capacity": self.v_2 * self.number_of_cells,
            "min_soc": self.min_soc
        }
