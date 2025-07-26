"""A simulator for carbon-aware applications and systems."""

from vessim.actor import Actor, PrometheusActor
from vessim.controller import Controller, Monitor
from vessim.cosim import Microgrid, Environment
from vessim.policy import MicrogridPolicy, DefaultMicrogridPolicy
from vessim.signal import Signal, Trace, StaticSignal
from vessim.storage import Storage, SimpleBattery, ClcBattery

__all__ = [
    "Actor",
    "PrometheusActor",
    "Controller",
    "Monitor",
    "Microgrid",
    "Environment",
    "MicrogridPolicy",
    "DefaultMicrogridPolicy",
    "StaticSignal",
    "Signal",
    "Trace",
    "Storage",
    "ClcBattery",
    "SimpleBattery",
]

try:
    from vessim.plot import plot_trace, plot_microgrid_trace  # noqa: F401

    __all__.extend(["plot_trace", "plot_microgrid_trace"])
except ImportError:
    pass

try:
    from vessim.controller import RestInterface  # noqa: F401

    __all__.extend(["RestInterface"])
except ImportError:
    # GUI controller requires optional dependencies: pip install vessim[vis]
    pass
