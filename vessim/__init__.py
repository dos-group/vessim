"""A simulator for carbon-aware applications and systems."""

from vessim.actor import Actor
from vessim.controller import Controller, MemoryLogger, CsvLogger
from vessim.dispatch_policy import DispatchPolicy, DefaultDispatchPolicy
from vessim.dispatchable import Dispatchable, Storage, SimpleBattery, ClcBattery
from vessim.environment import Environment
from vessim.microgrid import Microgrid
from vessim.signal import Signal, Trace, StaticSignal

__all__ = [
    "Actor",
    "Controller",
    "MemoryLogger",
    "CsvLogger",
    "Microgrid",
    "Environment",
    "DispatchPolicy",
    "DefaultDispatchPolicy",
    "Dispatchable",
    "Storage",
    "SimpleBattery",
    "ClcBattery",
    "StaticSignal",
    "Signal",
    "Trace",
]

try:
    from vessim.controller import Api  # noqa: F401
    from vessim.signal import SilSignal, WatttimeSignal, PrometheusSignal  # noqa: F401

    __all__.extend(["Api", "SilSignal", "WatttimeSignal", "PrometheusSignal"])
except ImportError:
    _SIL_INSTALL_MSG = (
        "This feature requires the 'sil' extra. Install with: pip install 'vessim[sil]'"
    )

    def __getattr__(name: str):
        if name in ("Api", "SilSignal", "WatttimeSignal", "PrometheusSignal"):
            raise ImportError(f"vessim.{name} is not available. {_SIL_INSTALL_MSG}")
        raise AttributeError(f"module 'vessim' has no attribute {name!r}")
