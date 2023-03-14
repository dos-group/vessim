"""
This module contains the agent to the consumption controller.
Author: Marvin Steinke

Notes: unts are in KW

"""

class ConsumptionAgent:
    def __init__(self, kW_conversion_factor = 1, battery_charge_rate = 100, battery_max_discharge = 1000):
        self.kW_conversion_factor = kW_conversion_factor
        self.battery_charge_rate = battery_charge_rate
        self.battery_max_discharge = battery_max_discharge
        self.consumption = 0

    def set_consumption(self, consumption):
        self.consumption = consumption * self.kW_conversion_factor
