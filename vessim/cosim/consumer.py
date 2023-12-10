from typing import Dict

from vessim.core.consumer import Consumer as _Consumer
from vessim.core.consumer import ComputingSystem
from vessim.cosim._util import SimWrapper, VessimSimulator, VessimModel


class Consumer(SimWrapper):
    def __init__(self, consumer: _Consumer) -> None:
        sim_name = type(self).__name__
        factory_name = sim_name + "Sim"
        super().__init__(factory_name, sim_name)
        self.consumer = consumer

    def _factory_args(self):
        return (self.sim_name,), {"step_size": self.cosim_data.step_size}

    def _sim_args(self):
        return (), {"consumer": self.consumer}
 

class ConsumerSim(VessimSimulator):
    """Computing System simulator that executes its model."""

    META = {
        "type": "time-based",
        "models": {
            "Consumer": {
                "public": True,
                "params": ["consumer"],
                "attrs": ["p", "info"],
            },
        },
    }

    def __init__(self):
        self.step_size = None
        super().__init__(self.META, _ComputingSystemModel)

    def init(self, sid, time_resolution, step_size, eid_prefix=None):
        self.step_size = step_size
        return super().init(sid, time_resolution, eid_prefix=eid_prefix)

    def finalize(self) -> None:
        """Stops power meters' threads."""
        super().finalize()
        for model_instance in self.entities.values():
            model_instance.consumer.finalize()  # type: ignore

    def next_step(self, time):
        return time + self.step_size


class _ComputingSystemModel(VessimModel):

    def __init__(self, consumer: _Consumer):
        self.consumer = consumer
        self.p = 0.0
        self.info: Dict = {}

    def step(self, time: int, inputs: dict) -> None:
        """Updates the power consumption of the system.

        The power consumption is calculated as the product of the PUE and the
        sum of the node power of all power meters.
        """
        self.p = -self.consumer.consumption()
        self.info = self.consumer.info()
