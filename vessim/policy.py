from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional, Literal, Any

from loguru import logger

if TYPE_CHECKING:
    from vessim.storage import Storage


class MicrogridPolicy(ABC):
    """Policy that describes how the microgrid deals with specific power deltas.

    The policy manages energy excess and shortage of a microgrid. It can model the
    (dis-)charging of a vessim `Storage`, the exchange of energy with the public grid, and things
    like curtailment of energy.
    Every `Microgrid` in a vessim co-simulation has a policy, and if not specified, the
    `DefaultMicrogridPolicy` is used. The policy is thereby applied at every time-step with the
    current power-delta and the duration of the time-step.
    """

    @abstractmethod
    def apply(self, p_delta: float, duration: int, storage: Optional[Storage] = None) -> float:
        """Function that applies the policy given a power delta.

        Args:
            p_delta: Power in W that the has to be served/stored. If positive, there is excess
                power and if negative, there is a lack of power. This is the power delta of all
                actors inside a simulation.
            duration: Time that the power delta is valid for. This is the microgrid step_size
                inside a simulation.
            storage: Optional storage that can be used to (dis)charge. This is the storage of the
                microgrid inside a simulation.

        Returns:
            Power in W that has benn drawn from (negative values) or fed to (positive values)
            the public grid during the last step.
        """

    def set_parameter(self, key: str, value: Any) -> None:
        """Fuction to let a controller update a policy parameter during a simulation using Mosaik.

        In the default case, the attribute with the name of the key is set on the policy object.
        The function can be subclassed to allow other ways of setting parameters.
        """
        if not hasattr(self, key):
            logger.warning(f"Attribute {key} of policy was never previously set.")
        setattr(self, key, value)

    def state(self) -> dict:
        """Returns information about the current state of the policy. Should be overridden."""
        return {}


class DefaultMicrogridPolicy(MicrogridPolicy):
    """Policy that is used as default for simulations.

    Policy tries to (dis)charge as much of the delta as possible using the storage if available.
    In `grid-connected` mode the public utility grid is used to exchange the remaining energy delta
    (positive or negative). In `islanded` mode, an error is raised when the power consumption
    exceeds the available power as no power can be drawn from the grid.

    Args:
        mode: Defines the mode that the microgrid operates in. In `grid-connected` mode, the
            microgrid can draw power from and feed power to the utility grid at will, whereas
            in `islanded` mode, the microgrid has to rely on its own energy resources.
            Default is `grid-connected`. Can be altered during simulation.
        charge_power: Additional power that can be specified to charge/discharge microgrid storage
            at specific rate (e.g. charge_power of 5 would charge the battery at exactly 5W).
            It only works in grid-connected mode and if a storage is present.
            Defaults to None. Can be altered during simulation.
    """

    def __init__(
        self,
        mode: Literal["grid-connected", "islanded"] = "grid-connected",
        charge_power: Optional[float] = None,
    ):
        self.mode = mode
        self.charge_power = charge_power if charge_power else 0.0

    def apply(self, p_delta: float, duration: int, storage: Optional[Storage] = None) -> float:
        energy_delta = p_delta * duration
        if self.mode == "grid-connected" and storage is not None:
            if self.charge_power:
                energy_delta -= storage.update(self.charge_power, duration)
            else:
                energy_delta -= storage.update(p_delta, duration)
        elif self.mode == "islanded":
            if storage:
                energy_delta -= storage.update(p_delta, duration)
            if energy_delta < 0.0:
                raise RuntimeError("Not enough energy available to operate in islanded mode.")
            energy_delta = 0.0
        return energy_delta / duration  # Convert energy to power (p_grid)

    def state(self) -> dict:
        """Returns current `mode` and `charge_power` values."""
        return {
            "mode": self.mode,
            "charge_power": self.charge_power,
        }
