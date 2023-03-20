"""
This module contains a simple energy grid model.
Author: Marvin Steinke

"""

import csv
from typing import Generator, Union

class SimpleEnergyGridModel:
    """
    This EnergyGridModel reads carbon information from a csv dataset either
    line by line, or for a given time. The conversion_factor is used to convert
    the carbon unit (e.g. from lb to kg: conversion_factor~=0,453592).
    """
    def __init__(self, datafile, conversion_factor=1, sim_start=0):
        self.datafile = datafile
        self.conversion_factor = conversion_factor
        self.sim_start = sim_start
        self.carbon = 0.0
        self.carbon_generator = self.generator()

    """
    Returns a generator, yielding the carbon values from self.datafile.
    """
    def generator(self) -> Generator[float, None, None]:
        with open(self.datafile, 'r') as f:
            reader = csv.reader(f)
            for _ in range(2):
                next(reader)
            for line in reader:
                yield float(line[1]) * self.conversion_factor

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
