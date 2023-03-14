"""
PV Controller. Acts as medium between pv module and ecovisor or direct consumer
since producer is only a csv generator.
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
    def __init__(self):
        super().__init__(META, PVAgent)

    def step(self, time, inputs, max_advance):
        self.time = time
        for agent_eid, attrs in inputs.items():
            agent = self.entities[agent_eid]
            production_dict = attrs.get('solar_power', {})
            if len(production_dict) > 0:
                agent.set_production(list(production_dict.values())[0])
        return None

def main():
    return mosaik_api.start_simulation(PVController())
