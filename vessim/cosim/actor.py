from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List

from vessim import TimeSeriesApi
from vessim.core.power_meters import PowerMeter
from vessim.cosim._util import VessimSimulator, VessimModel, Clock


class Actor(ABC):
    """Abstract base class representing a power consumer or producer."""

    def __init__(self, name: str, step_size: int):
        self.name = name
        self.step_size = step_size

    @abstractmethod
    def p(self, now: datetime) -> float:
        """Return the power consumption/production of the actor."""

    def info(self, now: datetime) -> Dict:
        """Return additional information about the state of the actor."""
        return {}

    def finalize(self) -> None:
        """Perform any finalization tasks for the consumer.

        This method can be overridden by subclasses to implement necessary
        finalization steps.
        """
        return


class ComputingSystem(Actor):
    """Model of the computing system.

    This model considers the power usage effectiveness (PUE) and power
    consumption of a list of power meters.

    Args:
        power_meters: A list of PowerMeter objects
            representing power meters in the system.
        pue: The power usage effectiveness of the system.
    """

    def __init__(self, name: str, step_size: int, power_meters: List[PowerMeter], pue: float = 1):
        super().__init__(name, step_size)
        self.power_meters = power_meters
        self.pue = pue

    def p(self, now: datetime) -> float:
        return self.pue * sum(-pm.measure() for pm in self.power_meters)

    def info(self, now: datetime) -> Dict:
        return {pm.name: -pm.measure() for pm in self.power_meters}

    def finalize(self) -> None:
        for power_meter in self.power_meters:
            power_meter.finalize()


class Generator(Actor):

    def __init__(self, name: str, step_size: int, time_series_api: TimeSeriesApi):
        super().__init__(name, step_size)
        self.time_series_api = time_series_api

    def p(self, now: datetime) -> float:
        return self.time_series_api.actual(now)  # TODO TimeSeriesApi must be for a single region


class ActorSim(VessimSimulator):
    """Computing System simulator that executes its model."""

    META = {
        "type": "time-based",
        "models": {
            "ActorModel": {
                "public": True,
                "params": ["actor"],
                "attrs": ["p", "info"],
            },
        },
    }

    def __init__(self):
        self.step_size = None
        super().__init__(self.META, _ActorModel)

    def init(self, sid, time_resolution, sim_start: datetime, step_size: int):  # TODO interfaces don't match with base class
        self.step_size = step_size
        self.clock = Clock(sim_start)
        return super().init(sid, time_resolution)

    def create(self, num, model, *args, **kwargs):
        return super().create(num, model, *args, **kwargs, clock=self.clock)

    def finalize(self) -> None:
        """Stops power meters' threads."""
        super().finalize()
        self.entity.actor.finalize()  # TODO it's not nice that it's unclear here that entity.actor is of type Actor

    def next_step(self, time):
        return time + self.step_size


class _ActorModel(VessimModel):

    def __init__(self, actor: Actor, clock: Clock):
        self.actor = actor
        self._clock = clock
        self.p = 0.0
        self.info: Dict = {}

    def step(self, time: int, inputs: dict) -> None:
        """Updates the power consumption of the system.

        The power consumption is calculated as the product of the PUE and the
        sum of the node power of all power meters.
        """
        now = self._clock.to_datetime(time)
        self.p = self.actor.p(now)
        self.info = self.actor.info(now)
