"""A simulator for carbon-aware applications and systems."""

from vessim.actor import ActorBase, Actor
from vessim.controller import Controller, Monitor
from vessim.cosim import Microgrid, Environment
from vessim.policy import MicrogridPolicy, DefaultMicrogridPolicy
from vessim.signal import Signal, Trace, ConstantSignal, CollectorSignal
from vessim.storage import Storage, SimpleBattery, ClcBattery

__all__ = [
    "ActorBase",
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
