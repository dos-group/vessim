"""
This module contains a simple battery model.
Author: Marvin Steinke

"""

class SimpleBatteryModel:
    """
    Simple battery model that changes its *charge* by *delta* every step.
    The battery's *capacity* is specified in kWh.
    If *init_charge* is not specified, it defaults to the *capacity*.
    *delta* must be specified in kWs.

    """
    def __init__(self, capacity = 100, init_charge = -1):
        self.capacity = capacity
        self.charge = init_charge if init_charge > -1 else capacity
        if self.charge > self.capacity:
            raise ValueError('The charge must not exceed its capacity')
        self.delta = 0

    def step(self):
        # convert Ws to Wh and add to *charge*
        self.charge += self.delta / 3600
        if self.charge > self.capacity:
            self.charge = self.capacity
        elif self.charge < 0:
            self.charge = 0
