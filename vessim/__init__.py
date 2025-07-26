"""A simulator for carbon-aware applications and systems."""

from vessim.actor import Actor
from vessim.controller import Controller, Monitor
from vessim.cosim import Microgrid, Environment
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
    from vessim.sil import PrometheusActor  # noqa: F401

    __all__.extend(["PrometheusActor"])
except ImportError:
    # SiL components require optional dependencies: pip install vessim[sil]
    pass

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
