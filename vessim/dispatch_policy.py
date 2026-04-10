from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional, Literal

from vessim.dispatchable import Storage

if TYPE_CHECKING:
    from vessim.dispatchable import Dispatchable


class DispatchPolicy(ABC):
    """Policy that describes how a microgrid dispatches power across dispatchables.

    The dispatch policy manages energy excess and shortage of a microgrid by allocating
    power across dispatchable resources (batteries, generators, etc.) and exchanging
    remaining energy with the public grid.
    """

    @abstractmethod
    def apply(
        self,
        p_delta: float,
        duration: int,
        dispatchables: list[Dispatchable],
        grid_signals: Optional[dict[str, float]] = None,
    ) -> float:
        """Allocate power delta across dispatchables.

        Args:
            p_delta: Power imbalance in W. Positive means excess power (can charge),
                negative means power deficit (need to discharge/generate).
            duration: Duration of the timestep in seconds.
            dispatchables: List of flexible components available for dispatch,
                like batteries or on-site diesel or gas generators.
            grid_signals: Current grid signal values (e.g., carbon intensity, energy
                price, curtailment), if any are configured on the microgrid.

        Returns:
            Power in W exchanged with the public grid. Negative means power drawn
            from the grid, positive means power fed to the grid.
        """

    def state(self) -> dict:
        """Returns information about the current state of the policy."""
        return {}


class DefaultDispatchPolicy(DispatchPolicy):
    """Default dispatch policy that allocates power in list order.

    Iterates through dispatchables in the order they are given and allocates as much
    of the power delta as each can handle. Remaining power is exchanged with the
    public grid in grid-connected mode.

    Args:
        mode: Operating mode. In ``"grid-connected"`` mode, remaining power is
            exchanged with the grid. In ``"islanded"`` mode, an error is raised
            if the delta cannot be fully served by dispatchables.
        charge_power: Optional fixed charge/discharge rate applied to storage dispatchables.
            If set, storage is charged/discharged at this rate regardless of the power delta,
            and remaining dispatchables are dispatched sequentially as usual.
            Only works in grid-connected mode. Defaults to None.
    """

    def __init__(
        self,
        mode: Literal["grid-connected", "islanded"] = "grid-connected",
        charge_power: Optional[float] = None,
    ):
        self.mode = mode
        self.charge_power = charge_power if charge_power else 0.0

    def apply(
        self,
        p_delta: float,
        duration: int,
        dispatchables: list[Dispatchable],
        grid_signals: Optional[dict[str, float]] = None,
    ) -> float:
        remaining = p_delta
        force_charged = set()

        if self.charge_power and self.mode == "grid-connected":
            # Pre-pass: force-charge/discharge storage at specified rate
            for d in dispatchables:
                if isinstance(d, Storage):
                    lo, hi = d.feasible_range(duration)
                    power = max(lo, min(hi, self.charge_power))
                    d.set_power(power, duration)
                    remaining -= power
                    force_charged.add(d)

        # Sequential dispatch for remaining dispatchables
        for d in dispatchables:
            if d in force_charged:
                continue
            if remaining == 0:
                d.set_power(0.0, duration)
                continue

            lo, hi = d.feasible_range(duration)

            if remaining > 0:  # excess: try to charge (positive power)
                allocated = max(0.0, min(hi, remaining))
            else:  # deficit: try to discharge (negative power)
                allocated = min(0.0, max(lo, remaining))

            d.set_power(allocated, duration)
            remaining -= allocated

        if self.mode == "islanded":
            if remaining < 0:
                raise RuntimeError(
                    "Not enough energy available to operate in islanded mode."
                )
            remaining = 0.0

        return remaining  # p_grid

    def state(self) -> dict:
        return {
            "mode": self.mode,
            "charge_power": self.charge_power,
        }
