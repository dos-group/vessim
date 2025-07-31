from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

import mosaik_api_v3  # type: ignore

from vessim.signal import Signal


class Actor:
    """Consumer or producer based on a Signal."""

    def __init__(self, name: str, signal: Signal, step_size: Optional[int] = None) -> None:
        self.name = name
        self.step_size = step_size
        self.signal = signal

    def p(self, now: datetime) -> float:
        """Current power consumption/production."""
        return self.signal.now(at=now)

    def state(self, now: datetime) -> dict:
        """Current state of the actor which is passed to controllers on every step."""
        return {
            "name": self.name,
            "signal": str(self.signal),
            "p": self.p(now),
        }

    def finalize(self) -> None:
        self.signal.finalize()


class SilActor(ABC):
    """Marker base class for Software-in-the-Loop actors.

    The Environment class uses this to sanity check that
    SilActor are only used in real-time simulations.
    """

    def __init__(self, name: str, step_size: Optional[int] = None) -> None:
        self.name = name
        self.step_size = step_size

    @abstractmethod
    def p(self, now: datetime) -> float:
        """Current power consumption/production."""

    @abstractmethod
    def state(self, now: datetime) -> dict:
        """Current state of the actor which is passed to controllers on every step."""

    def finalize(self) -> None:
        """Finalize the actor, e.g., close connections."""


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
