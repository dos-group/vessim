"""A simulator for carbon-aware applications and systems."""
from vessim import cosim
from vessim._signal import Signal, HistoricalSignal

__all__ = [
    "Signal",
    "HistoricalSignal",
    "cosim",
]

try:
    import vessim.sil  # noqa: F401
    __all__.append("sil")
except ImportError:
    pass
