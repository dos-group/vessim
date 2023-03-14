"""
Mosaik interface for the Ecovisor.
Author: Marvin Steinke

"""

import mosaik_api
from utils.single_model_simulator import SingleModelSimulator # type: ignore
from models.ecovisor_model import EcovisorModel # type: ignore

META = {
    'type': 'time-based',
    'models': {
        'EcovisorModel': {
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

class Ecovisor(SingleModelSimulator):
    def __init__(self):
        super().__init__(META, EcovisorModel)

def main():
    return mosaik_api.start_simulation(Ecovisor())
