import mosaik_api


class ComputingSystem:
    def __init__(self, power_meters):
        self.power_meters = power_meters
        self.p_cons = 0
        # TODO implement e.g. PUE

    def step(self):
        p_cons = 0
        for power_meter in self.power_meters:
            p_node, p_applications = power_meter.power_usage()
            p_cons += p_node
        self.p_cons = p_cons


class ComputingSystemSim(mosaik_api.Simulator):
    def __init__(self):
        super().__init__({
            'type': 'time-based',
            'models': {
                'ComputingSystem': {
                    'public': True,
                    'params': ['power_meters'],
                    'attrs': ['p_cons'],
                },
            },
        })
        self.eid_prefix = 'ComputingSystem_'
        self.entities = {}  # Maps EIDs to model instances/entities
        self.time = 0

    def init(self, sid, time_resolution=1):
        self.time_resolution = time_resolution
        return self.meta

    def create(self, num=1, model="ComputingSystem", power_meters=None):
        assert num == 1
        assert model == "ComputingSystem"
        assert power_meters is not None and len(power_meters) >= 1
        next_eid = len(self.entities)
        entities = []
        for i in range(next_eid, next_eid + num):
            model_instance = ComputingSystem(power_meters)
            eid = '%s%d' % (self.eid_prefix, i)
            self.entities[eid] = model_instance
            entities.append({'eid': eid, 'type': model})
        return entities

    def step(self, time, inputs, max_advance):
        self.time = time
        for entity in self.entities.values():
            entity.step()
        return int(time + self.time_resolution)

    def get_data(self, outputs):
        data = {}
        for eid, attrs in outputs.items():
            model = self.entities[eid]
            data['time'] = self.time
            data[eid] = {}
            for attr in attrs:
                if attr not in self.meta['models']['ComputingSystem']['attrs']:
                    raise ValueError('Unknown output attribute: %s' % attr)

                # Get model.val or model.delta:
                data[eid][attr] = getattr(model, attr)

        return data


def main():
    return mosaik_api.start_simulation(ComputingSystemSim())


if __name__ == '__main__':
    main()
