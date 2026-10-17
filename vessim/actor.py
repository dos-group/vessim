from __future__ import annotations

from datetime import timedelta
from typing import Optional

from vessim._util import require_finite
from vessim.signal import Signal


class Actor:
    """A component whose power is determined outside the dispatch policy.

    Positive power generates electricity and negative power consumes it. Use
    Consumer or Producer for inputs expressed as nonnegative magnitudes. A
    controller may change an actor's power or model parameters. The resulting
    demand or generation is observed at the next scheduled actor update.

    Args:
        name: The name of the actor.
        power: Signed power in W, as a finite number or a Signal.
        step_size: Sampling interval in seconds. Defaults to the microgrid's
            interval. Must be a positive multiple of that interval.
    """

    _direction = 1
    _nonnegative = False

    def __init__(
        self,
        name: str,
        power: float | Signal,
        step_size: Optional[int] = None,
    ) -> None:
        self.name = name
        self.step_size = step_size
        self.power = power

    @property
    def power(self) -> float | Signal:
        """Power input in W. Assign a number or Signal to change future samples.

        Consumer and Producer inputs are nonnegative magnitudes. Actor inputs
        are signed. Assignment does not change an already sampled observation.
        """
        return self._power

    @power.setter
    def power(self, value: float | Signal) -> None:
        if not isinstance(value, Signal):
            self._validate_input(value)
        self._power = value

    def _validate_input(self, value: float) -> None:
        require_finite(value, f"Power input for actor '{self.name}'")
        if self._nonnegative and value < 0:
            raise ValueError(f"{type(self).__name__} '{self.name}' requires nonnegative power.")

    def _validate_sample(self, power: float) -> None:
        require_finite(power, f"Power from actor '{self.name}'")
        if self._nonnegative and power * self._direction < 0:
            raise ValueError(f"Sampled power has the wrong direction for '{self.name}'.")

    def config(self) -> dict:
        """Configuration for experiment export, captured before the first tick."""
        return {
            "name": self.name,
            "type": type(self).__name__,
            "power": str(self.power) if isinstance(self.power, Signal) else self.power,
            "step_size": self.step_size,
        }

    def sample(self, elapsed: timedelta | float) -> tuple[float, dict]:
        """Return signed power and diagnostic state from one scheduled update.

        Override this method for a custom model. Call super().sample(elapsed)
        to sample the configured input once, then extend the returned state.
        The engine records the returned power under the state's "power" key.
        State must not trigger another input sample or advance the model again.
        """
        value = self.power.at(elapsed) if isinstance(self.power, Signal) else self.power
        self._validate_input(value)
        power = self._direction * value
        return power, {"power": power}

    def finalize(self) -> None:
        """Release resources owned by a custom actor.

        The environment finalizes input signals separately, once per signal.
        """


class Consumer(Actor):
    """An actor consuming a nonnegative power input in W.

    Accepts a number or Signal. Sampled and recorded power is negative.
    Controllers can update power for subsequent samples. The dispatch policy
    balances the resulting demand but does not choose this component's power.

    Args:
        name: The name of the consumer.
        power: Nonnegative demand in W, as a finite number or a Signal.
        step_size: Sampling interval in seconds, defaulting to the microgrid's
            interval. Must be a positive multiple of that interval.
    """

    _direction = -1
    _nonnegative = True


class Producer(Actor):
    """An actor generating a nonnegative power input in W.

    Accepts a number or Signal. Sampled and recorded power is positive.
    Use Actor for signed inputs that alternate between consumption and generation.

    Args:
        name: The name of the producer.
        power: Nonnegative generation in W, as a finite number or a Signal.
        step_size: Sampling interval in seconds, defaulting to the microgrid's
            interval. Must be a positive multiple of that interval.
    """

    _nonnegative = True
