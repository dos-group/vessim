"""
This module contains the agent to the pv controller.
Author: Marvin Steinke

Notes: unts are in KW

"""

class PVAgent:
    def __init__(self, kW_conversion_factor = 1):
        self.kW_conversion_factor = kW_conversion_factor
        self.solar_power = 0

    def set_production(self, production):
        self.solar_power = abs(production * self.kW_conversion_factor)
