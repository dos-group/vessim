from __future__ import annotations

from datetime import datetime
from typing import Optional

import mosaik_api_v3  # type: ignore

from vessim.signal import Signal


class Actor:
    """Consumer or producer based on a Signal.

    Args:
        name: The name of the actor.
        signal: The signal that determines the power consumption/production.
        step_size: The step size of the actor in seconds. If None, the step size
            of the microgrid is used.
    """

    def __init__(self, name: str, signal: Signal, step_size: Optional[int] = None) -> None:
        self.name = name
        self.step_size = step_size
        self.signal = signal

    def power(self, now: datetime) -> float:
        """Current power consumption/production."""
        return self.signal.now(at=now)

    def state(self, now: datetime) -> dict:
        """Current state of the actor which is passed to controllers on every step."""
        return {
            "name": self.name,
            "signal": str(self.signal),
            "power": self.power(now),
        }

    def finalize(self) -> None:
        """Clean up resources."""
        self.signal.finalize()


class _ActorSim(mosaik_api_v3.Simulator):
    META = {
        "type": "time-based",
        "models": {
            "Actor": {
                "public": True,
                "params": ["actor"],
                "attrs": ["power", "state"],
            },
        },
    }

    def __init__(self):
        super().__init__(self.META)
        self.eid = None
        self.step_size = None
        self.clock = None
        self.actor = None
        self.power = 0
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
        self.power = self.actor.power(now)
        self.state = self.actor.state(now)
        assert self.step_size is not None
        return time + self.step_size

    def get_data(self, outputs):
        return {self.eid: {"power": self.power, "state": self.state}}
