"""
A simple data collector that prints all data and saves it to a csv when the
simulation finishes.

"""
import collections
import mosaik_api
import csv
from tabulate import tabulate

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
        for attr, values in data.items():
            for src, value in values.items():
                self.data[src][attr][time] = value
        return None

    def finalize(self):
        print('Collected data:')
        for sim, sim_data in sorted(self.data.items()):
            table = []
            for attr, values in sorted(sim_data.items()):
                row = [attr]
                for value in values.values():
                    if attr == 'battery_charge_level':
                        value = value * 3600
                    row.append(f'{value:3.2f}')
                table.append(row)
            end = list(list(sim_data.values())[0].keys())[-1] + 1
            headers = [str(i) for i in list(range(end))]
            csv_data = [headers] + table
            with open("data.csv", "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerows(zip(*csv_data))
            headers.insert(0, sim)
            print(f'\n{tabulate(table, headers=headers)}')

if __name__ == '__main__':
    mosaik_api.start_simulation(Collector())
