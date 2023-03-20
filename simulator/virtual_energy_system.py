"""
Mosaik interface for the VirtualEnergySystem.
Author: Marvin Steinke

"""

import mosaik_api
from single_model_simulator import SingleModelSimulator
from models.virtual_energy_system_model import VirtualEnergySystemModel

META = {
    'type': 'time-based',
    'models': {
        'VirtualEnergySystemModel': {
            'public': True,
            'params': [
                'carbon_datafile',
                'carbon_conversion_factor',
                'sim_start',
                'battery_capacity',
                'battery_charge_level'
            ],
            'attrs': [
                'consumption',
                'battery_charge_rate',
                'battery_discharge_rate',
                'battery_max_discharge',
                'battery_charge_level',
                'battery_delta',
                'solar_power',
                'grid_carbon',
                'grid_power',
                'total_carbon',
            ],
        },
    },
}

class VirtualEnergySystem(SingleModelSimulator):
    def __init__(self):
        super().__init__(META, VirtualEnergySystemModel)

def main():
    return mosaik_api.start_simulation(VirtualEnergySystem())
