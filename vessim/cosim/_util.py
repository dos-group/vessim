from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Type, Dict, Any, Union, Tuple, List
from dataclasses import dataclass
from loguru import logger
from copy import deepcopy
import pandas as pd
import sys

from vessim.core.storage import Storage, StoragePolicy
from mosaik.scenario import World, Entity
import mosaik_api  # type: ignore


@dataclass
class CosimData:
    sim_start: str
    duration: int
    storage: Storage
    storage_policy: StoragePolicy
    rt_factor: float
    step_size: int


class SimWrapper(ABC):

    def __init__(self, factory_name: str, sim_name: str) -> None:
        self.factory_name = factory_name
        self.sim_name = sim_name
        self.cosim_data = None
        self.sim = None
        self.factory = None

    def get_config(self) -> dict:
        sim_address = ".".join(__name__.split(".")[:-1]) + f":{self.factory_name}"
        return {self.sim_name: {"python": sim_address}}

    @abstractmethod
    def _factory_args(self) -> Tuple[Tuple[Any, ...], Dict[str, Any]]:
        pass

    @abstractmethod
    def _sim_args(self) -> Tuple[Tuple[Any, ...], Dict[str, Any]]:
        pass

    def start(self, world: World, cosim_data: CosimData) -> Entity:
        self.cosim_data = deepcopy(cosim_data)
        factory_args, factory_kwargs = self._factory_args()
        self.factory = world.start(*factory_args, **factory_kwargs)
        sim_args, sim_kwargs = self._sim_args()
        self.sim = getattr(self.factory, self.sim_name)(*sim_args, **sim_kwargs)
        return self.sim


class VessimCoordinator:

    def __init__(
        self, 
        sim_start: str, 
        duration: int, 
        storage: Storage, 
        storage_policy: StoragePolicy,
        rt_factor: Union[float, None] = None,
        step_size: int = 60
    ) -> None:
        self.cosim_data = CosimData(
            sim_start, 
            duration, 
            storage, 
            storage_policy, 
            rt_factor, 
            step_size
        )
        self.cosim_config: Dict[str, Dict[str, str]] = {}
        self.sim_wrappers: List[SimWrapper] = []
        self.connections: List[Tuple] = []
        self.world = None

    def start_sim(self, sim_wrapper: SimWrapper) -> None:
        self.sim_wrappers.append(sim_wrapper)
        self.cosim_config.update(sim_wrapper.get_config())

    def connect(
        self,
        src: SimWrapper,
        dest: SimWrapper,
        *attr_pairs: Union[str, Tuple[str, str]],
        async_requests: bool = False,
        time_shifted: bool = False,
        initial_data: Dict[str, Any] = {},
        weak: bool = False
    ) -> None:
        args = (src, dest) + attr_pairs
        kwargs = {
            "async_requests": async_requests,
            "time_shifted": time_shifted,
            "initial_data": initial_data,
            "weak": weak
        }
        self.connections.append((args, kwargs))

    def run_cosim(self) -> None:
        self.world = World(self.cosim_config)
        for sim_wrapper in self.sim_wrappers:
            sim_wrapper.start(self.world, self.cosim_data)
        for args, kwargs in self.connections:
            # Replace src: SimWrapper and dest: SimWrapper from args with their sim Entity
            current_src, current_dest, *rest = args
            new_args = (current_src.sim, current_dest.sim) + tuple(rest)
            # Finnally call Mosaiks connect()
            self.world.connect(*new_args, **kwargs)
        self.world.run(
            until=self.cosim_data.duration, 
            rt_factor=self.cosim_data.rt_factor
        )


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
