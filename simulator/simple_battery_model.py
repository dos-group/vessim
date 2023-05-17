class SimpleBatteryModel:
    """(Way too) simple battery."""

    def __init__(
        self,
        capacity: float,
        charge_level: float,
        max_discharge: float,
        c_rate: float,
        step_size: int,
    ):
        """Initialization of a SimpleBattery instance.

        Args:
            capacity: Battery capacity in Ws
            charge_level: Initial charge level in Ws
            max_discharge: Minimum allowed soc for the battery
            c_rate: C-rate (https://www.batterydesign.net/electrical/c-rate/)
            step_size: currently not used
        """
        self.capacity = capacity
        assert 0 <= charge_level <= self.capacity
        self.charge_level = charge_level
        assert 0 <= max_discharge <= self.charge_level
        self.max_discharge = max_discharge
        assert 0 < c_rate
        self.max_charge_power = c_rate * self.capacity / 3600
        assert 0 < step_size
        self.step_size = step_size

    def step(self, power) -> float:
        """Can be called during simulation to feed or draw energy.

        If `energy` is positive the battery is charged.
        If `energy` is negative the battery is discharged.

        Returns the excess energy after the update:
        - Positive if your battery is fully charged
        - Negative if your battery is empty
        - else 0
        """
        # TODO implement exceeding max charge power
        assert power <= self.max_charge_power, (
            f"Cannot charge {power} W: Exceeding max charge power of "
            f"{self.max_charge_power}."
        )
        assert power >= -self.max_charge_power, (
            f"Cannot discharge {power} W: Exceeding max discharge power of "
            f"{self.max_charge_power}."
        )

        # step_size seconds of charging
        self.charge_level += power * self.step_size

        excess_power = 0

        # TODO: implement conversion losses
        abs_max_discharge = self.max_discharge * self.capacity
        if self.charge_level < abs_max_discharge:
            excess_power = (self.charge_level - abs_max_discharge) / self.step_size
            self.charge_level = abs_max_discharge
        elif self.charge_level > self.capacity:
            excess_power = (self.charge_level - self.capacity) / self.step_size
            self.charge_level = self.capacity

        return excess_power

    def soc(self):
        """Get the state of charge of the battery."""
        return self.charge_level / self.capacity
