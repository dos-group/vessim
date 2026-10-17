import math
from numbers import Real
from typing import Any
from collections.abc import Iterable


def require_finite(value: float, name: str) -> None:
    """Reject invalid physical inputs before they enter simulation arithmetic."""
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number, got {value!r}.")


def require_balanced(p_delta: float, powers: Iterable[float]) -> None:
    """Require an exactly zero residual after subtracting powers in dispatch order."""
    remaining = p_delta
    for power in powers:
        remaining -= power
    require_finite(remaining, "Remaining power delta")
    if remaining != 0:
        reason = "Unmet demand" if remaining < 0 else "Unabsorbed surplus"
        raise RuntimeError(f"{reason} of {abs(remaining):g} W: dispatch must balance exactly.")


def flatten_dict(d: dict, parent_key: str = "") -> dict:
    items: list[tuple[str, Any]] = []
    for k, v in d.items():
        # Escape path separators and the escape character to preserve distinct keys.
        key = k.replace("%", "%25").replace(".", "%2E")
        new_key = parent_key + "." + key if parent_key else key
        if isinstance(v, dict):
            items.extend(flatten_dict(v, str(new_key)).items())
        else:
            items.append((new_key, v))
    return dict(items)
