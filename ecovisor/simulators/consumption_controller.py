"""
Consumption Controller. Acts as medium between consumer and smart charge
controller or direct producer since consumer is only a csv generator.
Author: Marvin Steinke

"""

import mosaik_api
from agents.consumption_agent import ConsumptionAgent # type: ignore
from utils.single_model_simulator import SingleModelSimulator # type: ignore

META = {
    'type': 'event-based',
    'models': {
        'ConsumptionAgent': {
            'public': True,
            'params': ['kW_conversion_factor'],
            'attrs': ['consumption', 'battery_charge_rate', 'battery_max_discharge'],
        },
    },
}

class ConsumptionController(SingleModelSimulator):
    def __init__(self):
        super().__init__(META, ConsumptionAgent)

    def step(self, time, inputs, max_advance):
        self.time = time
        for agent_eid, attrs in inputs.items():
            agent = self.entities[agent_eid]
            consumption_dict = attrs.get('consumption', {})
            if len(consumption_dict) > 0:
                agent.set_consumption(list(consumption_dict.values())[0])
        return None

def main():
    return mosaik_api.start_simulation(ConsumptionController())
