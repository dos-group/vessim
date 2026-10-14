from __future__ import annotations

from datetime import timedelta
from typing import Optional

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
        consumer: If True, the signal value is negated (Vessim convention: consumption
            is negative, production is positive). Defaults to False.
        step_size: The step size of the actor in seconds. If None, the step size
            of the microgrid is used.
    """

    def __init__(
        self,
        name: str,
        signal: Signal,
        consumer: bool = False,
        step_size: Optional[int] = None,
    ) -> None:
        self.name = name
        self.step_size = step_size
        self.signal = signal
        self.consumer = consumer

    def power(self, elapsed: timedelta | float) -> float:
        """Current power consumption/production at `elapsed` time since `sim_start`."""
        value = self.signal.at(elapsed)
        return -value if self.consumer else value

    def config(self) -> dict:
        """Static configuration of the actor. Used for experiment config export."""
        return {
            "name": self.name,
            "signal": str(self.signal),
            "consumer": self.consumer,
            "step_size": self.step_size,
        }

    def state(self, elapsed: timedelta | float) -> dict:
        """Dynamic state of the actor at `elapsed` time since `sim_start`.

        This can be extended to include any relevant information about e.g. internal
        states of simulators that may be useful for control (e.g. temperature) or logs.
        """
        return {"power": self.power(elapsed)}

    def finalize(self) -> None:
        """Clean up resources."""
        self.signal.finalize()

    def sample(self, elapsed: timedelta | float) -> tuple[float, dict]:
        """Sample power and state once per actor update.

        The default state reuses sampled power. Overrides of ``state`` are
        still called; expensive custom actors can override this method to
        return both values from one computation.
        """
        power = self.power(elapsed)
        default_state = type(self).state is Actor.state and "state" not in self.__dict__
        state = {"power": power} if default_state else self.state(elapsed)
        return power, state
