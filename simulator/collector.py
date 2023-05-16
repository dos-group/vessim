import collections
import csv
from loguru import logger

import mosaik_api


META = {
    'type': 'event-based',
    'models': {
        'Monitor': {
            'public': True,
            'any_inputs': True,
            'params': [],
            'attrs': [],
        },
    },
}


class Collector(mosaik_api.Simulator):
    """Simple data collector that prints all data when the simulation finishes. """

    def __init__(self):
        super().__init__(META)
        self.eid = None
        self.data = collections.defaultdict(lambda: collections.defaultdict(dict))

    def init(self, sid, time_resolution):
        return self.meta

    def create(self, num, model):
        if num > 1 or self.eid is not None:
            raise RuntimeError('Can only create one instance of Monitor.')

        self.eid = 'Monitor'
        return [{'eid': self.eid, 'type': model}]

    def step(self, time, inputs, max_advance):
        data = inputs.get(self.eid, {})
        logger.info(f"# {str(time):>5} ----------")
        for attr, values in data.items():
            for src, value in values.items():
                logger.info(f"{src}[{attr}] = {value}")
                self.data[src][attr][time] = value
        return None

    def finalize(self):
        print('Collected data:')
        for _, sim_data in sorted(self.data.items()):
            table = []
            for attr, values in sorted(sim_data.items()):
                row = [attr]
                for value in values.values():
                    row.append(f'{value:3.2f}')
                table.append(row)
            end = list(list(sim_data.values())[0].keys())[-1] + 1
            time_column = [str(i) for i in list(range(end))]
            time_column[0] = 'time'
            csv_data = [time_column] + table
            with open("data.csv", "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerows(zip(*csv_data))
