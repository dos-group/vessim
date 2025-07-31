"""A simulator for carbon-aware applications and systems."""

from vessim.actor import Actor
from vessim.controller import Controller, Monitor
from vessim.environment import Environment
from vessim.microgrid import Microgrid
from vessim.policy import MicrogridPolicy, DefaultMicrogridPolicy
from vessim.signal import Signal, Trace, StaticSignal
from vessim.storage import Storage, SimpleBattery, ClcBattery

__all__ = [
    "Actor",
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
    from vessim.controller import Api  # noqa: F401

    __all__.extend(["Api"])
except ImportError:
    # GUI controller requires optional dependencies: pip install vessim[vis]
    pass

try:
    from vessim.signal import SilSignal, WatttimeSignal, PrometheusSignal  # noqa: F401

    __all__.extend(["SilSignal", "WatttimeSignal", "PrometheusSignal"])
except ImportError:
    # WatttimeSignal and PrometheusSignal require optional dependencies: pip install vessim[sil]
    pass
