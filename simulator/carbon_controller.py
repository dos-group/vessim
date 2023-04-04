"""Carbon Controller.

Acts as a medium between carbon module and ecovisor or direct consumer since
producer is only a CSV generator.

Author: Marvin Steinke
"""

import mosaik_api
from simulator.models.carbon_agent import CarbonAgent  # type: ignore
from simulator.single_model_simulator import SingleModelSimulator

# Metadata for the CarbonAgent model
META = {
    'type': 'event-based',
    'models': {
        'CarbonAgent': {
            'public': True,
            'params': ['carbon_conversion_factor'],
            'attrs': ['carbon_intensity'],
        },
    },
}


class CarbonController(SingleModelSimulator):
    """Class that represents the Carbon Controller."""

    def __init__(self):
        """Constructor for the Carbon Controller."""
        super().__init__(META, CarbonAgent)


def main():
    """Main function that starts the simulation."""
    return mosaik_api.start_simulation(CarbonController())
