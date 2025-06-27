from __future__ import annotations

from datetime import datetime
from typing import Optional
from abc import ABC, abstractmethod

import mosaik_api_v3  # type: ignore

from vessim.signal import Signal


class ActorBase(ABC):
    """Abstract base class representing a power consumer or producer."""

    def __init__(self, name: str, step_size: Optional[int] = None) -> None:
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


class Actor(ActorBase):
    """Actor that represents a consumer of producer based on a single Signal."""

    def __init__(self, name: str, signal: Signal, step_size: Optional[int] = None) -> None:
        super().__init__(name, step_size)
        self.signal = signal

    def p(self, now: datetime) -> float:
        return self.signal.now(at=now)

    def state(self, now: datetime) -> dict:
        return {
            "p": self.p(now),
        }

    def finalize(self) -> None:
        self.signal.finalize()



class _ActorSim(mosaik_api_v3.Simulator):
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
        assert self.step_size is not None
        return time + self.step_size

    def get_data(self, outputs):
        return {self.eid: {"p": self.p, "state": self.state}}
