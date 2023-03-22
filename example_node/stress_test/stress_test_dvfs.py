#!/usr/bin/env python3

import os
import sys
import subprocess
sys.path.append('../lib')
import time
from pi_monitor import PiMonitor # type: ignore
import csv


class Data():
    def __init__(self) -> None:
        self.current = []
        self.voltage = []
        self.power = []
        self.freqency = []
        self.time = []

    def add_entry(self, time: int, current: float, voltage: float, power: float, frequency: int) -> None:
        self.time.append(time)
        self.current.append(current)
        self.voltage.append(voltage)
        self.power.append(power)
        self.freqency.append(frequency)

    def to_dict(self) -> dict:
        return {"time": self.time,
                "frequency": self.freqency,
                "power": self.power,
                "current": self.current,
                "voltage": self.voltage}


def save_dict_to_csv(data_dict, filename):
    with open(filename, mode="w", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(data_dict.keys())
        # Determine the number of rows to write
        num_rows = max([len(lst) for lst in data_dict.values()])
        # Write the data rows
        for i in range(num_rows):
            row = [data_dict[key][i] if i < len(data_dict[key]) else "" for key in data_dict.keys()]
            writer.writerow(row)


def gather_data(monitor, frequency, runtime):
    # set specific frequency to use
    monitor.set_max_frequency(frequency)
    # give time to adjust
    time.sleep(3)
    # start sysbench
    process = subprocess.Popen(["sysbench", f"--time={runtime}", "--threads=4", "cpu", "run"])
    data = Data()
    # gather data for runtime
    time_passed = 1
    while process.poll() is None:
        data.add_entry(time=time_passed,
                       current=monitor.current(),
                       voltage=monitor.voltage(),
                       power=monitor.power(),
                       frequency=frequency)
        time_passed += 1
        time.sleep(1)
    return data


# runtime is specified in minutes at cli level
runtime = int(sys.argv[1]) * 60
monitor = PiMonitor()
directory = "data"
if not os.path.exists(directory):
    os.makedirs(directory)

for frequency in monitor.available_frequencies:
    data = gather_data(monitor, frequency, runtime)
    output_file = f"{directory}/{int(frequency/1000)}.csv"
    save_dict_to_csv(data.to_dict(), output_file)
