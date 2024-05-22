"""A simulator for carbon-aware applications and systems."""
from vessim.actor import Actor, ComputingSystem, Generator
from vessim.controller import Controller, Monitor
from vessim.cosim import Microgrid, Environment
from vessim.policy import MicrogridPolicy, DefaultMicrogridPolicy
from vessim.power_meter import PowerMeter, MockPowerMeter
from vessim.signal import Signal, HistoricalSignal
from vessim.storage import Storage, SimpleBattery

__all__ = [
    "Actor",
    "ComputingSystem",
    "Generator",
    "Controller",
    "Monitor",
    "Microgrid",
    "Environment",
    "MicrogridPolicy",
    "DefaultMicrogridPolicy",
    "PowerMeter",
    "MockPowerMeter",
    "Signal",
    "HistoricalSignal",
    "Storage",
    "SimpleBattery",
]

try:
    from vessim.sil import Broker, SilController, WatttimeSignal, get_latest_event  # noqa: F401
    __all__.extend(["Broker", "SilController", "WatttimeSignal", "get_latest_event"])
except ImportError:
    pass
