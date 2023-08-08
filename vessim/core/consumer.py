from abc import ABC, abstractmethod
from typing import Optional


class PowerMeter(ABC):
    """Abstract base class for power meters.

    Args:
        name: The name of the power meter.
    """

    def __init__(self, name: Optional[str] = None):
        self.name = name

    @abstractmethod
    def measure(self) -> float:
        """Abstract method to measure and return the current node power demand.

        Returns:
            float: The current power demand of the node.
        """
        pass

    @abstractmethod
    def finalize(self) -> None:
        pass


class MockPowerMeter(PowerMeter):
    """A mock power meter class.

    This class is used to simulate the behavior of a power meter with various
    modes. The power meter supports different power modes that are: 'high
    performance', 'normal', and 'power-saving'.

    Raises:
        ValueError: If p is less than 0.
        ValueError: If the power modes in `power_config` are not 'power-saving',
            'normal', and 'high performance'.

    Attributes:
        p: A factor to modify the measured power value.
        power_mode: The current power mode, default is 'high performance'.
        power_config: A dictionary mapping power modes to their respective
            consumption factors, defaults to
            {"high performance": 1, "normal": .7, "power-saving": .5}.

    """

    def __init__(
        self, p: float,
        name: Optional[str] = None,
        power_config: dict[str, float] = {
            "high performance": 1,
            "normal": .7,
            "power-saving": .5
        }
    ):
        super().__init__(name)
        if p < 0:
            raise ValueError("p must not be less than 0")
        self.p = p
        self.power_modes = {"power-saving", "normal", "high performance"}
        self.power_mode = "high performance"
        if set(power_config.keys()) != self.power_modes:
            raise ValueError(f"power_config keys must be exactly {self.power_modes}")
        self.power_config = power_config

    def measure(self) -> float:
        """Measures the current power.

        The measurement is the product of the power factor 'p' and the power
        configuration for the current mode.

        Returns:
            float: The measured power.
        """
        return self.p * self.power_config[self.power_mode]

    def finalize(self) -> None:
        pass

    def set_power_mode(self, power_mode: str) -> None:
        """Sets the power mode of the meter.

        Args:
            power_mode (str): The power mode to set.

        Raises:
            ValueError: If the power mode is not one of 'power-saving',
                'normal', or 'high performance'.
        """
        if power_mode not in self.power_modes:
            raise ValueError(
                f"{power_mode} is not a valid power mode. "
                "Available power modes: {self.power_modes}"
            )
        self.power_mode = power_mode


class Consumer(ABC):

    @abstractmethod
    def consumption(self) -> float:
        pass

    def finalize(self) -> None:
        pass


class ComputingSystem(Consumer):
    """Model of the computing system.

    This model considers the power usage effectiveness (PUE) and power
    consumption of a list of power meters.

    Args:
        power_meters: A list of PowerMeter objects
            representing power meters in the system.
        pue: The power usage effectiveness of the system.
    """

    def __init__(self, power_meters: list[PowerMeter], pue: float = 1):
        self.power_meters = power_meters
        self.pue = pue

    def consumption(self) -> float:
        return self.pue * sum(pm.measure() for pm in self.power_meters)

    def finalize(self) -> None:
        for power_meter in self.power_meters:
            power_meter.finalize()
