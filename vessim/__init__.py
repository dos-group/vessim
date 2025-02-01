"""A simulator for carbon-aware applications and systems."""

from vessim.actor import ActorBase, Actor, ComputingSystem
from vessim.controller import Controller, Monitor
from vessim.cosim import Microgrid, Environment
from vessim.policy import MicrogridPolicy, DefaultMicrogridPolicy
from vessim.signal import Signal, HistoricalSignal, MockSignal, CollectorSignal
from vessim.storage import Storage, Battery, BatteryDegradation, SimpleBattery, ClcBattery

__all__ = [
    "ActorBase",
    "Actor",
    "ComputingSystem",
    "Controller",
    "Monitor",
    "Microgrid",
    "Environment",
    "MicrogridPolicy",
    "DefaultMicrogridPolicy",
    "CollectorSignal",
    "MockSignal",
    "Signal",
    "HistoricalSignal",
    "Storage",
    "Battery",
    "BatteryDegradation",
    "ClcBattery",
    "SimpleBattery",
]

try:
    from vessim.storage import ModelDegradation  # noqa: F401

    __all__.extend(["ModelDegradation"])
except ImportError:
    pass

try:
    from vessim.sil import Broker, SilController, WatttimeSignal, get_latest_event  # noqa: F401

    __all__.extend(["Broker", "SilController", "WatttimeSignal", "get_latest_event"])
except ImportError:
    pass
