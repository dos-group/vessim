from __future__ import annotations

from datetime import datetime
from itertools import count
from typing import Optional

import mosaik_api_v3  # type: ignore

from vessim.signal import Signal


class Actor:
    """Base class representing a power consumer or producer."""

    def __init__(
        self, name: str, signal: Optional[Signal] = None, step_size: Optional[int] = None
    ):
        self.name = name
        self.signal = signal
        self.step_size = step_size

    def p(self, now: datetime) -> float:
        """Current power consumption/production to be used in the grid simulation."""
        if self.signal is None:
            raise ValueError("A Signal needs to be specified.")
        data_point = self.signal.at(now)
        assert data_point is not None
        return data_point

    def state(self, now: datetime) -> dict:
        """Current state of the actor to be used in controllers."""
        return {
            "p": self.p(now),
        }

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
        signals: list of consumer node signals that constitute the computing system's demand.
        pue: The power usage effectiveness of the system.
    """

    _ids = count(0)

    def __init__(
        self,
        nodes: list[Signal],
        name: Optional[str] = None,
        step_size: Optional[int] = None,
        pue: float = 1,
    ):
        if name is None:
            name = f"ComputingSystem-{next(self._ids)}"
        super().__init__(name, step_size=step_size)
        self.nodes = nodes
        node_ids = count(0)
        for node in self.nodes:
            if not node.name:
                node.name = f"Node-{next(node_ids)}"
        self.pue = pue

    def p(self, now: datetime) -> float:
        return self.pue * sum(-signal.at(now) for signal in self.nodes)  # type: ignore

    def state(self, now: datetime) -> dict:
        return {
            "p": self.p(now),
            "nodes": {signal.name: -signal.at(now) for signal in self.nodes},  # type: ignore
        }


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
