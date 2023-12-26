from datetime import datetime
from typing import Dict

from vessim.core.actor import Actor
from vessim.cosim._util import VessimSimulator, VessimModel, Clock


class ActorSim(VessimSimulator):
    """Computing System simulator that executes its model."""

    META = {
        "type": "time-based",
        "models": {
            "ActorModel": {
                "public": True,
                "params": ["actor"],
                "attrs": ["p", "info"],
            },
        },
    }

    def __init__(self):
        self.step_size = None
        super().__init__(self.META, _ActorModel)

    def init(self, sid, time_resolution, sim_start: datetime, step_size: int, eid_prefix=None):  # TODO interfaces don't match with base class
        self.step_size = step_size
        self.clock = Clock(sim_start)
        return super().init(sid, time_resolution, eid_prefix=eid_prefix)

    def create(self, num, model, *args, **kwargs):
        return super().create(num, model, *args, **kwargs, clock=self.clock)

    def finalize(self) -> None:
        """Stops power meters' threads."""
        super().finalize()
        for model_instance in self.entities.values():  # TODO we only want a single actor per simulator
            model_instance.actor.finalize()  # TODO it's not nice that it's unclear here that model_instance.actor is of type Actor

    def next_step(self, time):
        return time + self.step_size

    # TODO the old GeneratorSim was able to automatically step to the next available item
    #   do we still want and need this?
    # def next_step(self, time: int) -> int:
    #     dt = self.clock.to_datetime(time)
    #     next_dt = min(e.generator.next_update(dt)   # type: ignore
    #                   for e in self.entities.values())
    #     return self.clock.to_simtime(next_dt)


class _ActorModel(VessimModel):

    def __init__(self, actor: Actor, clock: Clock):  # TODO revise if this clock is still the most meaninful way to manage time
        self.actor = actor
        self._clock = clock
        self.p = 0.0
        self.info: Dict = {}

    def step(self, time: int, inputs: dict) -> None:
        """Updates the power consumption of the system.

        The power consumption is calculated as the product of the PUE and the
        sum of the node power of all power meters.
        """
        now = self._clock.to_datetime(time)
        self.p = self.actor.p(now)
        self.info = self.actor.info(now)
