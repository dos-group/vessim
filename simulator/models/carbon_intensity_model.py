"""
This module contains a simple carbon intensity model.
Author: Marvin Steinke

"""

import csv
from typing import Generator, Union
from datetime import datetime

class CarbonIntensityModel:
    """
    This CarbonIntensityModel reads carbon information from a csv dataset either
    line by line, or for a given time. The conversion_factor is used to convert
    the carbon unit (e.g. from lb to kg: conversion_factor~=0,453592).
    """
    def __init__(self, datafile, conversion_factor=1, sim_start=0, step_size=1):
        self.datafile = datafile
        self.conversion_factor = conversion_factor
        self.sim_start = sim_start
        self.step_size = step_size
        self.carbon = 0.0
        self.carbon_generator = self.generator()

    """
    Returns a generator, yielding the carbon values from self.datafile.
    """
    def generator(self) -> Generator[float, None, None]:
        with open(self.datafile, 'r') as f:
            reader = csv.reader(f)
            # first two lines only contain header
            for _ in range(2):
                next(reader)
            # yield first line of data
            first_line = next(reader)
            yield float(first_line[1] * self.conversion_factor)
            current_time = self.timestamp(first_line[0])
            for line in reader:
                next_timestamp = self.timestamp(line[0])
                if current_time > next_timestamp:
                    # the simulator time is ahead, continue until smaller or equal
                    continue
                while current_time <= next_timestamp:
                    # the simulator time is either behind or equal, yield
                    yield float(line[1]) * self.conversion_factor
                    current_time += self.step_size

    def timestamp(self, datetime_str: str) -> float:
        return datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S").timestamp()

    """
    Steps the generator.
    """
    def step(self) -> None:
        try:
            self.carbon = next(self.carbon_generator)
        except StopIteration:
            raise ValueError('The dataset has ended')

    """
    Return a carbon value for a given time, if it exists.
    """
    def get_carbon(self, time) -> Union[float, Exception]:
        with open(self.datafile, 'r') as f:
            reader = csv.reader(f)
            for _ in range(2):
                next(reader)
            for line in reader:
                if time in line:
                    return float(line[1]) * self.conversion_factor
        raise ValueError(f'No carbon entry was found for {time}')
