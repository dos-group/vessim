from cpufreq import cpuFreq # type: ignore
from ina219 import INA219 # type: ignore
import psutil


class PiController:
    """This class represents a controller for the Raspberry Pi system.

    For providing information and control about power and CPU usage of
    a raspberry pi using ina219 and cpufreq.
    """

    def __init__(self) -> None:
        self.ina = INA219(0.1, address=0x45)
        self.ina.configure()
        self.cpu = cpuFreq()
        self.available_frequencies = self.cpu.available_frequencies

    def current(self) -> float:
        """Get the current in Amps being drawn by the Raspberry Pi.

        Returns:
            The current being drawn by the Pi.
        """
        return round(self.ina.current(), 2)

    def voltage(self) -> float:
        """Get the voltage in Volts being supplied to the Raspberry Pi.

        Returns:
            The voltage being supplied to the Pi.
        """
        return round(self.ina.voltage(), 2)

    def power(self) -> float:
        """Get the power in Watts being consumed by the Raspberry Pi.

        Returns:
            The power being consumed by the Pi.
        """
        return round(self.ina.power() / 1000, 2)

    def frequency(self) -> int:
        """Get the current frequency in MHz of the CPU of the Raspberry Pi.

        Returns:
            The current frequency of the CPU.
        """
        return self.cpu.get_frequencies()[0]

    def frequency_index(self) -> int:
        """Get the index of the current CPU frequency of available frequencies.

        Returns:
            The index of the current CPU frequency.
        """
        return self.available_frequencies.index(self.frequency())

    def set_max_frequency(self, frequency) -> None:
        """Set the maximum frequency for the CPU of the Raspberry Pi.

        Args:
            frequency: The maximum frequency to set.
        """
        self.cpu.set_max_frequencies(frequency)

    def cpu_util(self) -> float:
        """Get the current CPU utilization as a percentage.

        Returns:
            The current CPU utilization.
        """
        return psutil.cpu_percent(1)
