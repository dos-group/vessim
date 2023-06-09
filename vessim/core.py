from abc import ABC, abstractmethod
from typing import Type, Dict

import mosaik_api


class VessimModel:

    @abstractmethod
    def step(self, time: int, inputs: dict) -> None:
        """Performs a simulation step on the model.

        Args:
            time: The current simulation time
            inputs: The inputs from other simulators
        """


class VessimSimulator(mosaik_api.Simulator, ABC):
    """Utility class for single-model simulators as supported by Vessim.

    Most use cases for simulators simply require setting all inputs attr values
    to model_instance attrs and then step the model_instance. This class takes
    care of all basic mosaik abstractions that are simple copy and paste tasks
    for each new simulator.

    Attributes:
        eid_prefix: The prefix to be used for entity IDs.
        model_class: The class of the model to be simulated.
        entities: A dictionary that maps entity IDs to their instances.
        time: The current simulation time.
        step_size: The simulation step size.
    """

    def __init__(self, meta, model_class: Type[VessimModel]):
        """Initialization of a basic simulator with given model.

        Args:
            meta: A dictionary that describes the simulator's metadata.
            model_class: The class of the model to be simulated. Model requires
                step() method with no args (must only utilize object
                attributes). Alternatively, the step() method of this class
                must be overwritten and implemented individually.
        """
        super().__init__(meta)
        self.eid_prefix = list(self.meta["models"])[0] + "_"  # type: ignore
        self.model_class = model_class
        self.entities: Dict[int, VessimModel] = {}
        self.time = 0

    def init(self, sid, time_resolution, eid_prefix=None):
        """Initialize Simulator and set `step_size` and `eid_prefix`."""
        if float(time_resolution) != 1.0:
            raise ValueError(
                f"{self.__class__.__name__} only supports time_resolution=1., "
                f"but {time_resolution} was set."
            )
        if eid_prefix is not None:
            self.eid_prefix = eid_prefix
        return self.meta

    def create(self, num, model, *args, **kwargs):
        """Create model instance and save it in `entities`."""
        next_eid = len(self.entities)
        entities = []
        for i in range(next_eid, next_eid + num):
            # Instantiate `model_class` specified in constructor and pass through args
            entity = self.model_class(*args, **kwargs)
            eid = self.eid_prefix + str(i)
            self.entities[eid] = entity
            entities.append({"eid": eid, "type": model})
        return entities

    def step(self, time, inputs, max_advance):
        """Set all `inputs` attr values to the `entity` attrs, then step the `entity`."""
        self.time = time

        input_mapping: Dict[VessimModel, Dict] = {}
        for eid, attrs in inputs.items():
            # We assume a single input per value -> take first item from dict
            inputs_ = {key: list(val_dict.values())[0] for key, val_dict in attrs.items()}
            input_mapping[eid] = inputs_

        for eid, entity in self.entities.items():
            entity.step(time, input_mapping.get(eid, {}))

        return self.next_step(time)

    @abstractmethod
    def next_step(self, time):
        """Return time of next simulation step (None for event-based)."""

    def get_data(self, outputs):
        """Return all requested data as attr from the `model_instance`."""
        data = {}
        model_name = list(self.meta["models"])[0]  # type: ignore
        for eid, attrs in outputs.items():
            model = self.entities[eid]
            data["time"] = self.time
            data[eid] = {}
            for attr in attrs:
                if attr not in self.meta["models"][model_name]["attrs"]:  # type: ignore
                    raise ValueError(f"Unknown output attribute: {attr}")
                if hasattr(model, attr):
                    data[eid][attr] = getattr(model, attr)
        return data
