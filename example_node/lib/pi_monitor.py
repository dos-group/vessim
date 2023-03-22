from cpufreq import cpuFreq
from ina219 import INA219
import psutil

class PiMonitor():
    def __init__(self) -> None:
        self.ina = INA219(0.1, address=0x45)
        self.ina.configure()
        self.cpu = cpuFreq()
        self.available_frequencies = self.cpu.available_frequencies

    # returns current in mA
    def current(self) -> float:
        return round(self.ina.current(), 2)

    # returns voltage in V
    def voltage(self) -> float:
        return round(self.ina.voltage(), 2)

    # returns power in W
    def power(self) -> float:
        return round(self.ina.power(), 2)

    # returns frequency in kHz
    def frequency(self) -> int:
        return self.cpu.get_frequencies()[0]

    # returns the index of self.frequency() from self.available_frequencies
    def frequency_index(self) -> int:
        return self.available_frequencies.index(self.frequency())

    # sets maximum frequency in kHz
    def set_max_frequency(self, frequency) -> None:
        self.cpu.set_max_frequencies(frequency)

    # return the cpu utilization measured over 1 second
    def cpu_util(self) -> float:
        return psutil.cpu_percent(1)
