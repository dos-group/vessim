import math
from numbers import Real
from typing import Any


def require_finite(value: float, name: str) -> None:
    """Reject invalid physical inputs before they enter simulation arithmetic."""
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number, got {value!r}.")


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
