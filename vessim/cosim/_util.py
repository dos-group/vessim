import sys
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Type, Dict, Any, Union

import mosaik_api  # type: ignore
import pandas as pd
from loguru import logger


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
        self.eid_prefix = list(self.meta["models"])[0] + "_"
        self.model_class = model_class
        self.entities: Dict[str, VessimModel] = {}
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
        for eid, entity in self.entities.items():
            entity.step(time, inputs.get(eid, {}))
        return self.next_step(time)

    @abstractmethod
    def next_step(self, time):
        """Return time of next simulation step (None for event-based)."""

    def get_data(self, outputs):
        """Return all requested data as attr from the `model_instance`."""
        data = {}
        model_name = list(self.meta["models"])[0]
        for eid, attrs in outputs.items():
            model = self.entities[eid]
            data["time"] = self.time
            data[eid] = {}
            for attr in attrs:
                if attr not in self.meta["models"][model_name]["attrs"]:
                    raise ValueError(f"Unknown output attribute: {attr}")
                if hasattr(model, attr):
                    data[eid][attr] = getattr(model, attr)
        return data


class Clock:
    def __init__(self, sim_start: Union[str, datetime]):
        self.sim_start = pd.to_datetime(sim_start)

    def to_datetime(self, simtime: int) -> datetime:
        return self.sim_start + timedelta(seconds=simtime)

    def to_simtime(self, dt: datetime) -> int:
        return int((dt - self.sim_start).total_seconds())


def simplify_inputs(attrs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Removes Mosaik source entity from input dict.

    Examples:
        >>> simplify_inputs({'p': {'ComputingSystem-0.ComputingSystem_0': -50}})
        {'p': -50}
    """
    # TODO We should make this function a bit more elegant once we better evaluated
    #   our requirements for Vessim simulations.
    result = {}
    for key, val_dict in attrs.items():
        result[key] = list(val_dict.values())[0]
        # flattening dicts
        if isinstance(result[key], dict):
            for kk in result[key].keys():
                result[f"{key}.{kk}"] = result[key][kk]
            del result[key]
    return result


def disable_mosaik_warnings(behind_threshold: float):
    """Disables Mosaik's incorrect Loguru warnings.

    Mosaik currently deems specific attribute connections as incorrect and logs
    them as warnings. Also the simulation is always behind by a few fractions
    of a second (which is fine, code needs time to execute) which Mosaik also
    logs as a Warning. These Warnings are flagged as bugs in Mosaik's current
    developement and should be fixed within its next release. Until then, this
    function should do.

    Args:
        behind_threshold: Time the simulation is allowed to be behind schedule.
    """
    # Define a function to filter out WARNING level logs
    def filter_record(record):
        is_warning = record["level"].name == "WARNING"
        is_mosaik_log = record["name"].startswith("mosaik")
        is_attribute = record["function"] == "_check_attributes_values"
        is_below_threshold = (
            record["function"] == "rt_check" and
            float(record["message"].split(' - ')[1].split('s')[0]) < behind_threshold
        )
        return not (is_warning and is_mosaik_log and (is_below_threshold or is_attribute))

    # Add the filter to the logger
    logger.remove()
    logger.add(sys.stdout, filter=filter_record)
