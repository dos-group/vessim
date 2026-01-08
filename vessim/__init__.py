"""A simulator for carbon-aware applications and systems."""

from vessim.actor import Actor
from vessim.controller import Controller, MemoryLogger, CsvLogger
from vessim.environment import Environment
from vessim.microgrid import Microgrid
from vessim.policy import Policy, DefaultPolicy
from vessim.signal import Signal, Trace, StaticSignal
from vessim.storage import Storage, SimpleBattery, ClcBattery

__all__ = [
    "Actor",
    "Controller",
    "MemoryLogger",
    "CsvLogger",
    "Microgrid",
    "Environment",
    "Policy",
    "DefaultPolicy",
    "StaticSignal",
    "Signal",
    "Trace",
    "Storage",
    "ClcBattery",
    "SimpleBattery",
]

try:
    from vessim.controller import Api  # noqa: F401
    from vessim.signal import SilSignal, WatttimeSignal, PrometheusSignal  # noqa: F401

    __all__.extend(["Api", "SilSignal", "WatttimeSignal", "PrometheusSignal"])
except ImportError:
    # Requires optional dependencies: pip install vessim[sil]
    pass

try:
    from vessim.plot import plot_trace, plot_result_df  # noqa: F401

    __all__.extend(["plot_trace", "plot_result_df"])
except ImportError:
    # Requires optional dependencies: pip install vessim[vis]
    pass
