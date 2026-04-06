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
    # Requires optional dependencies: pip install vessim[sil]
    pass
