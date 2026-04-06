from __future__ import annotations

from datetime import datetime
from typing import Optional

import mosaik_api_v3  # type: ignore

from vessim.signal import Signal


class Actor:
    """An exogenous energy consumer or producer based on a `Signal`.

    Actors represent non-dispatchable energy devices whose power output is
    determined externally like solar panels, wind turbines, or (compute) loads.

    Args:
        name: The name of the actor.
        signal: The `Signal` that determines the power consumption/production. Can be
            a `StaticSignal` for constant power, a `Trace` for time series data, or any
            custom signal (e.g., based on real-time monitoring).
        step_size: The step size of the actor in seconds. If None, the step size
            of the microgrid is used.
    """

    def __init__(
        self,
        name: str,
        signal: Signal,
        step_size: Optional[int] = None,
    ) -> None:
        self.name = name
        self.step_size = step_size
        self.signal = signal

    def power(self, now: datetime) -> float:
        """Current power consumption/production."""
        return self.signal.now(at=now)

    def config(self) -> dict:
        """Static configuration of the actor. Used for experiment config export."""
        return {
            "name": self.name,
            "signal_type": self.signal.__class__.__name__,
            "signal": str(self.signal),
            "step_size": self.step_size,
        }

    def state(self, now: datetime) -> dict:
        """Dynamic state of the actor at the current timestep, passed to `Controller`s.

        This can be extended to include any relevant information about e.g. internal
        states of simulators that may be useful for control (e.g. temperature) or logs.
        """
        return {"power": self.power(now)}

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
