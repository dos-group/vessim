from abc import ABC, abstractmethod
from datetime import datetime
from itertools import count
from typing import Dict, List, Optional

import mosaik_api

from vessim.core import TimeSeriesApi
from vessim.cosim.power_meter import PowerMeter


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
        power_meters: list of PowerMeters that constitute the computing system's demand.
        pue: The power usage effectiveness of the system.
    """
    _ids = count(0)

    def __init__(
        self,
        step_size: int,
        power_meters: List[PowerMeter],
        name: Optional[str] = None,
        pue: float = 1
    ):
        if name is None:
            name = f"ComputingSystem-{next(self._ids)}"
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
    _ids = count(0)

    def __init__(self, step_size: int, time_series_api: TimeSeriesApi, name: Optional[str] = None):
        if name is None:
            name = f"Generator-{next(self._ids)}"
        super().__init__(name, step_size)
        self.time_series_api = time_series_api

    def p(self, now: datetime) -> float:
        return self.time_series_api.actual(now)  # TODO TimeSeriesApi must be for a single region


class ActorSim(mosaik_api.Simulator):
    META = {
        "type": "time-based",
        "models": {
            "Actor": {
                "public": True,
                "params": ["actor"],
                "attrs": ["p", "info"],
            },
        },
    }

    def __init__(self):
        super().__init__(self.META)
        self.eid = None
        self.step_size = None
        self.clock = None
        self.actor = None
        self.p = 0
        self.info = {}

    def init(self, sid, time_resolution=1., **sim_params):
        self.step_size = sim_params["step_size"]
        self.clock = sim_params["clock"]
        return self.meta

    def create(self, num, model, **model_params):
        assert num == 1, "Only one instance per simulation is supported"
        self.actor = model_params["actor"]
        self.eid = self.actor.name
        return [{"eid": self.eid, "type": model}]

    def step(self, time, inputs, max_advance):
        now = self.clock.to_datetime(time)
        self.p = self.actor.p(now)
        self.info = self.actor.info(now)
        return time + self.step_size

    def get_data(self, outputs):
        return {self.eid: {"p": self.p, "info": self.info}}
