from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

from vessim.dispatchable import ClcBattery, GridConnection, SimpleBattery, Storage
from vessim._util import require_balanced, require_finite

if TYPE_CHECKING:
    from vessim.dispatchable import Dispatchable


_BUILTIN_DISPATCHABLES = (SimpleBattery, ClcBattery, GridConnection)


class DispatchPolicy(ABC):
    """Allocate power across controllable resources, including grid connections."""

    @abstractmethod
    def apply(
        self,
        p_delta: float,
        duration: float,
        dispatchables: list[Dispatchable],
        grid_signals: Optional[dict[str, float]] = None,
    ) -> None:
        """Assign feasible resource setpoints that fully balance the power delta.

        No value is returned. Microgrid validates setpoints and requires an exactly
        zero remaining delta after subtracting powers in resource order. Neither
        unmet demand nor surplus is accepted. Curtailment is not implicit.

        Args:
            p_delta: Power imbalance in W. Positive means excess power.
                Negative means a deficit.
            duration: Duration of the upcoming interval in seconds.
            dispatchables: Controllable resources in priority order, including
                any GridConnection. Every resource must receive a feasible setpoint.
            grid_signals: Current context such as energy price or carbon intensity.
        """

    def state(self) -> dict:
        """Return information about the current state of the policy."""
        return {}


class DefaultDispatchPolicy(DispatchPolicy):
    """Allocate power in list order while honoring every resource's constraints.

    Allocate power in priority order, reserving mandatory power for subsequent
    resources. Grid connections participate at their position in the list.
    If no balanced allocation is possible, raise RuntimeError before changing
    setpoints. Both unmet demand and unabsorbed surplus are errors.

    Args:
        charge_power: Optional fixed charge/discharge power in W for each Storage,
            clipped to its feasible range. Other resources balance these setpoints.
            Zero or None uses ordinary priority dispatch. If the fixed setpoints
            cannot be balanced, dispatch raises an error.
    """

    def __init__(self, charge_power: Optional[float] = None):
        if charge_power is not None:
            require_finite(charge_power, "charge_power")
        self.charge_power = charge_power if charge_power else 0.0

    def apply(
        self,
        p_delta: float,
        duration: float,
        dispatchables: list[Dispatchable],
        grid_signals: Optional[dict[str, float]] = None,
    ) -> None:
        self._apply(p_delta, duration, dispatchables)

    def _apply(
        self,
        p_delta: float,
        duration: float,
        dispatchables: list[Dispatchable],
        ranges: Optional[list[tuple[float, float]]] = None,
    ) -> None:
        """Allocate with optional bounds from the microgrid's current dispatch."""
        require_finite(p_delta, "Power delta")
        require_finite(self.charge_power, "charge_power")
        require_finite(duration, "Dispatch duration")
        if duration <= 0:
            raise ValueError("Dispatch duration must be positive.")
        reuse_ranges = ranges is not None
        if ranges is None:
            ranges = [d._validated_range(duration) for d in dispatchables]
        fixed = [bool(self.charge_power) and isinstance(d, Storage) for d in dispatchables]
        powers = [
            max(lo, min(hi, self.charge_power if force else 0))
            for (lo, hi), force in zip(ranges, fixed)
        ]
        # Reserve mandatory/fixed power from resources later in the list. Keep
        # the allocation and final validation in the same subtraction order.
        # The last flexible resource consumes the exact remaining delta.
        reserved = [0.0] * (len(powers) + 1)
        for i in range(len(powers) - 1, -1, -1):
            reserved[i] = powers[i] + reserved[i + 1]
            require_finite(reserved[i], "Reserved power")
        remaining = p_delta
        for i, ((lo, hi), force) in enumerate(zip(ranges, fixed)):
            if not force:
                target = remaining - reserved[i + 1] if reserved[i + 1] else remaining
                powers[i] = max(lo, min(hi, target))
            remaining -= powers[i]

        require_balanced(p_delta, powers)
        for d, power, bounds in zip(dispatchables, powers, ranges):
            if reuse_ranges:
                require_finite(power, f"Power setpoint for '{d.name}'")
                d._set_power_in_range(power, duration, bounds)
            else:
                d.set_power(power, duration)

    def state(self) -> dict:
        return {"charge_power": self.charge_power}
