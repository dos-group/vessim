class SimpleBatteryModel:
    """(Way too) simple battery.

    Args:
        capacity: Battery capacity in Ws
        charge_level: Initial charge level in Ws
        min_soc: Minimum allowed soc for the battery
        c_rate: C-rate (https://www.batterydesign.net/electrical/c-rate/)
    """
    def __init__(self, capacity: float, charge_level: float, min_soc: float, c_rate: float):
        self.capacity = capacity
        assert 0 <= charge_level <= self.capacity
        self.charge_level = charge_level
        # TODO min_soc is in % and charge_level in Ws, they should not be compared
        assert 0 <= min_soc <= self.charge_level
        self.min_soc = min_soc
        assert 0 < c_rate
        self.max_charge_power = c_rate * self.capacity / 3600

    def step(self, power: float, duration: int) -> float:
        """Can be called during simulation to feed or draw energy for a specified duration.

        Args:
            power:
                If `power` is positive, the battery is charged.
                If `power` is negative, the battery is discharged.
            duration:
                The duration in seconds for which the battery will be charged or discharged.

        Returns:
            The excess energy after the update:
                - Positive if your battery is fully charged
                - Negative if your battery is empty
                - else 0
        """
        # TODO implement exceeding max charge power
        assert power <= self.max_charge_power, f"Cannot charge {power} W: Exceeding max charge power of {self.max_charge_power}."
        assert power >= -self.max_charge_power, f"Cannot discharge {power} W: Exceeding max discharge power of {self.max_charge_power}."

        self.charge_level += power * duration  # duration seconds of charging
        excess_power = 0

        # TODO: implement conversion losses
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
