"""Mosaik interface for the VirtualEnergySystem.

Author: Marvin Steinke
"""

import mosaik_api
from simulator.single_model_simulator import SingleModelSimulator
from simulator.models.virtual_energy_system_model import VirtualEnergySystemModel


META = {
    'type': 'time-based',
    'models': {
        'VirtualEnergySystemModel': {
            'public': True,
            'params': [
                'battery_capacity',
                'battery_charge_level',
                'battery_max_discharge',
                'battery_c_rate',
            ],
            'attrs': [
                'consumption',
                'battery_max_discharge',
                'battery_charge_level',
                'solar_power',
                'grid_carbon',
                'grid_power',
                'total_carbon',
            ],
        },
    },
}


class VirtualEnergySystem(SingleModelSimulator):
    """VirtualEnergySystem class that inherits from SingleModelSimulator."""

    def __init__(self):
        super().__init__(META, VirtualEnergySystemModel)


def main():
    """Start the mosaik simulation."""
    return mosaik_api.start_simulation(VirtualEnergySystem())
