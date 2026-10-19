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
    ``finalize()`` returns this calculator's scalar or None when undefined.
    Attach constants and derived values with ExperimentResult.add_metric()
    after the run. Metrics must not change simulation components.

    Args:
        unit: Unit of the result, such as Wh, EUR, kgCO2e, or 1 for a ratio.
        microgrid: Microgrid name, or None for a run-level metric.
        actor: Actor name within microgrid, or None for a microgrid-level metric.
        description: Human-readable definition of the calculation.
        assumptions: JSON-compatible assumptions, such as lifetime or allocation rules.

    Attributes:
        value (float): Accumulated result, initialized to zero by start() and
            returned by the default finalize() implementation.
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

    def step(self, now: datetime, states: dict[str, MicrogridState], duration: float) -> None:
        """Accumulate one observation without retaining the trajectory."""

    def finalize(self) -> Optional[float]:
        """Return the final scalar computed by this calculator."""
        return self.value

    def definition(self) -> dict:
        """Describe the metric without embedding its calculation in the result."""
        return {
            "unit": self.unit,
            "description": self.description,
            "assumptions": self.assumptions,
        }


class _GridIntegral(Metric):
    def __init__(self, microgrid: str, signal: str, unit: str, direction: int, description: str):
        super().__init__(
            unit,
            microgrid=microgrid,
            description=description,
            assumptions={
                "factor_signal": signal,
                "factor_unit": f"{unit}/kWh",
                "period": "simulated_intervals",
            },
        )
        self.signal = signal
        self.direction = direction

    def start(self, environment: Environment) -> None:
        super().start(environment)
        assert self.microgrid is not None
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

    Args:
        microgrid: Name of the microgrid to evaluate.
        price: Grid signal containing the import price in currency/kWh.
        currency: Currency label for the resulting metric.
    """

    def __init__(self, microgrid: str, price: str, currency: str = "EUR"):
        super().__init__(microgrid, price, currency, -1, "Electricity import cost")


class ElectricityExportRevenue(_GridIntegral):
    """Integrate exported electricity times a sale price in currency/kWh.

    Args:
        microgrid: Name of the microgrid to evaluate.
        price: Grid signal containing the export price in currency/kWh.
        currency: Currency label for the resulting metric.
    """

    def __init__(self, microgrid: str, price: str, currency: str = "EUR"):
        super().__init__(microgrid, price, currency, 1, "Electricity export revenue")


class GridImportEmissions(_GridIntegral):
    """Integrate imported electricity times an emissions signal in kgCO2e/kWh.

    This excludes onsite fuel use and embodied emissions. Exported electricity
    does not offset the result. The supplied factor determines the accounting basis.

    Args:
        microgrid: Name of the microgrid to evaluate.
        carbon_intensity: Grid signal containing emissions intensity in kgCO2e/kWh.
    """

    def __init__(self, microgrid: str, carbon_intensity: str):
        super().__init__(
            microgrid,
            carbon_intensity,
            "kgCO2e",
            -1,
            "Emissions associated with imported electricity",
        )
