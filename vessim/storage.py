from abc import ABC, abstractmethod

from loguru import logger


class Storage(ABC):

    @abstractmethod
    def update(self, power: float, duration: int) -> float:
        """Feed or draw energy for specified duration.

        Args:
            power: Charging if positive, discharging if negative.
            duration: Duration in seconds for which the storage will be (dis)charged.

        Returns:
            The excess energy after the update: Positive if fully charged, negative if
            empty, 0 otherwise.
        """


class SimpleBattery(Storage):
    """(Way too) simple battery.

    Args:
        capacity: Battery capacity in Ws
        charge_level: Initial charge level in Ws
        min_soc: Minimum allowed soc for the battery
        c_rate: C-rate (https://www.batterydesign.net/electrical/c-rate/)
    """
    # TODO Test battery

    def __init__(self,
                 capacity: float,
                 charge_level: float,
                 min_soc: float,
                 c_rate: float):
        self.capacity = capacity
        assert 0 <= charge_level <= self.capacity
        self.charge_level = charge_level
        assert 0 <= min_soc <= self.soc()
        self.min_soc = min_soc
        assert 0 < c_rate
        self.max_charge_power = c_rate * self.capacity / 3600
        self.max_discharge_power = -c_rate * self.capacity / 3600

    def update(self, power: float, duration: int) -> float:
        if power <= self.max_charge_power:
            logger.info(f"Trying to charge storage '{__class__.__name__}' with "
                        f"{power}W but only {self.max_charge_power} are supported.")
            power = self.max_charge_power

        if power <= self.max_discharge_power:
            logger.info(f"Trying to discharge storage '{__class__.__name__}' with "
                        f"{power}W but only {self.max_discharge_power} are supported.")
            power = self.max_discharge_power

        self.charge_level += power * duration  # duration seconds of charging
        excess_power = 0.0

        abs_min_soc = self.min_soc * self.capacity
        if self.charge_level < abs_min_soc:
            excess_power = (self.charge_level - abs_min_soc) / duration
            self.charge_level = abs_min_soc
        elif self.charge_level > self.capacity:
            excess_power = (self.charge_level - self.capacity) / duration
            self.charge_level = self.capacity

        return excess_power

    def soc(self):
        return self.charge_level / self.capacity


class StoragePolicy(ABC):

    @abstractmethod
    def apply(self, storage: Storage, p_delta: float, time_since_last_step: int) -> float:
        """(Dis)charge the storage according to the policy"""


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
