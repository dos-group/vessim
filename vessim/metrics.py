"""Incremental metrics for experiment recording."""

from __future__ import annotations

import math
from datetime import datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from vessim.environment import Environment
    from vessim.microgrid import MicrogridState


class Metric:
    """A user-defined scalar metric, scoped to a run, microgrid, or actor.

    Override start(), step(), or finalize() as needed. ``duration`` is the
    observation's interval in seconds, clipped at the requested horizon.
    ``finalize`` receives all built-in metrics and earlier custom metrics in
    registration order. Return None when a value is undefined, such as a ratio
    with a zero denominator. Metrics must not change simulation components.

    Args:
        unit: Unit of the result, such as Wh, EUR, kgCO2e, or 1 for a ratio.
        microgrid: Microgrid name, or None for a run-level metric.
        actor: Actor name within microgrid, or None for a microgrid-level metric.
        description: Human-readable definition of the calculation.
        assumptions: JSON-compatible assumptions, such as lifetime or allocation rules.
    """

    def __init__(
        self,
        unit: str,
        *,
        microgrid: Optional[str] = None,
        actor: Optional[str] = None,
        description: str = "",
        assumptions: Optional[dict] = None,
    ):
        if not isinstance(unit, str) or not unit:
            raise ValueError("A metric must declare its unit.")
        if actor is not None and microgrid is None:
            raise ValueError("An actor metric requires a microgrid name.")
        self.unit = unit
        self.microgrid = microgrid
        self.actor = actor
        self.description = description
        self.assumptions = dict(assumptions or {})
        self.value = 0.0

    def start(self, environment: Environment) -> None:
        """Initialize counters or calculate scenario-dependent values."""
        self.value = 0.0

    def step(
        self, now: datetime, states: dict[str, MicrogridState], duration: float
    ) -> None:
        """Accumulate one observation without retaining the trajectory."""

    def finalize(self, metrics: dict) -> Optional[float]:
        """Return the final value or derive it from already completed metrics."""
        return self.value

    def definition(self) -> dict:
        """Describe the metric without embedding its calculation in the result."""
        return {
            "unit": self.unit,
            "description": self.description,
            "assumptions": self.assumptions,
        }


class ConstantMetric(Metric):
    """Record a supplied scenario value, such as CAPEX, embodied emissions, or area."""

    def __init__(self, value: float, unit: str, **kwargs):
        super().__init__(unit, **kwargs)
        if not math.isfinite(value):
            raise ValueError("A constant metric must be finite.")
        self._constant = float(value)

    def start(self, environment: Environment) -> None:
        self.value = self._constant


class _GridIntegral(Metric):
    def __init__(self, microgrid: str, signal: str, unit: str, direction: int, description: str):
        super().__init__(
            unit,
            microgrid=microgrid,
            description=description,
            assumptions={"factor_signal": signal, "factor_unit": f"{unit}/kWh",
                         "period": "simulated_intervals"},
        )
        self.signal = signal
        self.direction = direction

    def start(self, environment: Environment) -> None:
        super().start(environment)
        grid = environment.microgrids[self.microgrid]
        if self.signal not in (grid.grid_signals or {}):
            raise ValueError(f"Metric requires grid signal '{self.signal}' on '{self.microgrid}'.")

    def step(self, now, states, duration):
        state = states[self.microgrid]
        factor = (state["grid_signals"] or {}).get(self.signal)
        if factor is None or not math.isfinite(factor):
            raise ValueError(f"Metric signal '{self.signal}' must contain finite values.")
        power = max(0.0, self.direction * state["p_grid"])
        self.value += power * duration / 3_600_000 * factor


class ElectricityImportCost(_GridIntegral):
    """Integrate imported electricity times a price signal in currency/kWh.

    This excludes maintenance, demand charges, and other operating costs.
    Negative electricity prices are supported. No price signal is inferred.
    """

    def __init__(self, microgrid: str, price: str, currency: str = "EUR"):
        super().__init__(microgrid, price, currency, -1, "Electricity import cost")


class ElectricityExportRevenue(_GridIntegral):
    """Integrate exported electricity times an explicit sale price in currency/kWh."""

    def __init__(self, microgrid: str, price: str, currency: str = "EUR"):
        super().__init__(microgrid, price, currency, 1, "Electricity export revenue")


class GridImportEmissions(_GridIntegral):
    """Integrate imported electricity times an emissions signal in kgCO2e/kWh.

    This excludes onsite fuel use and embodied emissions. Exported electricity
    does not offset the result. The supplied factor determines the accounting basis.
    """

    def __init__(self, microgrid: str, carbon_intensity: str):
        super().__init__(microgrid, carbon_intensity, "kgCO2e", -1,
                         "Emissions associated with imported electricity")
