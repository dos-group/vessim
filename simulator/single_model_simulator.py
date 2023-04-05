import mosaik_api

class SingleModelSimulator(mosaik_api.Simulator):
    """ Generic class for single-model simulators or controllers: Many usecases
    for simulators simply require setting all inputs attr values to the
    model_instance attrs and then to step the model_instance. This class takes
    care of all basic mosaik abstractions that are simple copy and paste tasks
    for each new simulator.

    Args:
        META: A dictionary that describes the simulator's metadata.
        model_class: The class of the model to be simulated. Model requires a
        step() method with no args (must only utilizes object attributes).
        Alternatively the step() method of this class must be overwritten and
        implemented individually.

    Attributes:
        eid_prefix: The prefix to be used for entity IDs.
        model_class: The class of the model to be simulated.
        entities: A dictionary that maps entity IDs to their instances.
        time: The current simulation time.
        step_size: The simulation step size.
    """

    def __init__(self, META, model_class):
        super().__init__(META)
        self.eid_prefix = list(self.meta['models'])[0] + '_' # type: ignore
        self.model_class = model_class
        self.entities = {}
        self.time = 0
        self.step_size = 1

    def init(self, sid, time_resolution, step_size=1, eid_prefix=None):
        """Initialize Simulator and set `step_size` and `eid_prefix`."""
        if float(time_resolution) != 1.:
            raise ValueError(f'{self.__class__.__name__} only supports time_resolution=1., but {time_resolution} was set.')
        self.step_size = step_size
        if eid_prefix is not None:
            self.eid_prefix = eid_prefix
        return self.meta

    def create(self, num, model, *args, **kwargs):
        """Create `model_instance` and save it in `entities`."""
        next_eid = len(self.entities)
        entities = []
        for i in range(next_eid, next_eid + num):
            # Instantiate `model_class` specified in constructor and pass through args
            model_instance = self.model_class(*args, **kwargs)
            eid = self.eid_prefix + str(i)
            self.entities[eid] = model_instance
            entities.append({'eid': eid, 'type': model})
        return entities

    def step(self, time, inputs, max_advance):
        """Set all `inputs` attr values to the `model_instance` attrs, then step the `model_instance`."""
        self.time = time
        for eid, attrs in inputs.items():
            model_instance = self.entities[eid]
            if hasattr(model_instance, 'step_size'):
                setattr(model_instance, 'step_size', self.step_size)
            for attr, val_dict in attrs.items():
                if len(val_dict) > 0:
                    # Only one input per value expected -> take first item from dict
                    val = list(val_dict.values())[0]
                    # And set the attr for the `model_instance`
                    if hasattr(model_instance, attr):
                        setattr(model_instance, attr, val)
            model_instance.step()
        # Support all simulator types
        return None if self.meta['type'] == 'event-based' else time + self.step_size # type: ignore

    def get_data(self, outputs):
        """Return all requested data as attr from the `model_instance`."""
        data = {}
        model_name = list(self.meta['models'])[0] # type: ignore
        for eid, attrs in outputs.items():
            model = self.entities[eid]
            data['time'] = self.time
            data[eid] = {}
            for attr in attrs:
                if attr not in self.meta['models'][model_name]['attrs']: # type: ignore
                    raise ValueError(f'Unknown output attribute: {attr}')
                if hasattr(model, attr):
                    data[eid][attr] = getattr(model, attr)
        return data
