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
    from vessim.sil import Broker, SilController, WatttimeSignal, get_latest_event  # noqa: F401

    __all__.extend(["Broker", "SilController", "WatttimeSignal", "get_latest_event"])
except ImportError:
    pass

try:
    from vessim.plot import plot_trace, plot_microgrid_trace

    __all__.extend(["plot_trace", "plot_microgrid_trace"])
except ImportError:
    pass
