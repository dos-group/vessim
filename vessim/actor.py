from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from itertools import count
from typing import Optional

import mosaik_api  # type: ignore

from vessim.power_meter import PowerMeter
from vessim.signal import Signal


class Actor(ABC):
    """Abstract base class representing a power consumer or producer."""

    def __init__(self, name: str, step_size: Optional[int] = None):
        self.name = name
        self.step_size = step_size

    @abstractmethod
    def p(self, now: datetime) -> float:
        """Current power consumption/production to be used in the grid simulation."""

    def state(self, now: datetime) -> dict:
        """Current state of the actor to be used in controllers."""
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
        power_meters: list[PowerMeter],
        name: Optional[str] = None,
        step_size: Optional[int] = None,
        pue: float = 1,
    ):
        if name is None:
            name = f"ComputingSystem-{next(self._ids)}"
        super().__init__(name, step_size)
        self.power_meters = power_meters
        self.pue = pue

    def p(self, now: datetime) -> float:
        return self.pue * sum(-pm.measure() for pm in self.power_meters)

    def state(self, now: datetime) -> dict:
        return {
            "p": self.p(now),
            "power_meters": {pm.name: -pm.measure() for pm in self.power_meters},
        }

    def finalize(self) -> None:
        for power_meter in self.power_meters:
            power_meter.finalize()


class Generator(Actor):  # TODO signal should return next step
    _ids = count(0)

    def __init__(
        self, signal: Signal, step_size: Optional[int] = None, name: Optional[str] = None
    ):
        if name is None:
            name = f"Generator-{next(self._ids)}"
        super().__init__(name, step_size)
        self.signal = signal  # TODO make sure that signal is single column?

    def p(self, now: datetime) -> float:
        data_point = self.signal.at(now)
        assert data_point is not None
        return data_point

    def state(self, now: datetime) -> dict:
        return {
            "p": self.p(now),
        }


class ActorSim(mosaik_api.Simulator):
    META = {
        "type": "time-based",
        "models": {
            "Actor": {
                "public": True,
                "params": ["actor"],
                "attrs": ["p", "state"],
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
        self.state = {}

    def init(self, sid, time_resolution=1.0, **sim_params):
        self.step_size = sim_params["step_size"]
        self.clock = sim_params["clock"]
        return self.meta

    def create(self, num, model, **model_params):
        assert num == 1, "Only one instance per simulation is supported"
        self.actor = model_params["actor"]
        self.eid = self.actor.name
        return [{"eid": self.eid, "type": model}]

    def step(self, time, inputs, max_advance):
        assert self.clock is not None
        now = self.clock.to_datetime(time)
        assert self.actor is not None
        self.p = self.actor.p(now)
        self.state = self.actor.state(now)
        return time + self.step_size

    def get_data(self, outputs):
        return {self.eid: {"p": self.p, "state": self.state}}
