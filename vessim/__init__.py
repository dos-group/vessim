"""A simulator for carbon-aware applications and systems."""

from vessim.actor import Actor
from vessim.controller import Controller, Monitor
from vessim.cosim import Microgrid, Environment
from vessim.policy import MicrogridPolicy, DefaultMicrogridPolicy
from vessim.signal import Signal, Trace, ConstantSignal, CollectorSignal
from vessim.storage import Storage, SimpleBattery, ClcBattery

__all__ = [
    "Actor",
    "Controller",
    "Monitor",
    "Microgrid",
    "Environment",
    "MicrogridPolicy",
    "DefaultMicrogridPolicy",
    "CollectorSignal",
    "ConstantSignal",
    "Signal",
    "Trace",
    "Storage",
    "ClcBattery",
    "SimpleBattery",
]

try:
    from vessim.sil import PrometheusActor  # noqa: F401

    __all__.extend(["PrometheusActor"])
except ImportError:
    # SiL components require optional dependencies
    pass

try:
    from vessim.plot import plot_trace, plot_microgrid_trace  # noqa: F401

    __all__.extend(["plot_trace", "plot_microgrid_trace"])
except ImportError:
    pass
