""" PV Controller. 

Acts as medium between pv module and ecovisor or direct consumer since producer
is only a csv generator.

Author: Marvin Steinke

"""

import mosaik_api
from agents.pv_agent import PVAgent # type: ignore
from utils.single_model_simulator import SingleModelSimulator # type: ignore

META = {
    'type': 'event-based',
    'models': {
        'PVAgent': {
            'public': True,
            'params': ['kW_conversion_factor'],
            'attrs': ['solar_power'],
        },
    },
}

class PVController(SingleModelSimulator):
    """Class that represents the PV Controller."""

    def __init__(self):
        """Constructor for the PV Controller."""
        super().__init__(META, PVAgent)

def main():
    """Main function that starts the simulation."""
    return mosaik_api.start_simulation(PVController())
