import mosaik_api

from vessim import DefaultStoragePolicy


class GridSim(mosaik_api.Simulator):
    META = {
        "type": "event-based",
        "models": {
            "Grid": {
                "public": True,
                "params": ["storage", "policy"],
                "attrs": ["p", "p_delta"],
            },
        },
    }

    def __init__(self):
        super().__init__(self.META)
        self.eid = "Grid"
        self.storage = None
        self.policy = None
        self.p_delta = 0.0
        self._last_step_time = 0

    def create(self, num, model, **model_params):
        assert num == 1, "Only one instance per simulation is supported"
        self.storage = model_params["storage"]
        self.policy = model_params["policy"]
        if self.policy is None:
            self.policy = DefaultStoragePolicy()
        return [{"eid": self.eid, "type": model}]

    def step(self, time, inputs, max_advance):
        duration = time - self._last_step_time
        self._last_step_time = time
        if duration == 0:
            return
        p_delta = sum(inputs[self.eid]["p"].values())
        if self.storage is None:
            self.p_delta = p_delta
        else:
            self.p_delta = self.policy.apply(self.storage, p_delta, duration)

    def get_data(self, outputs):
        return {self.eid: {"p_delta": self.p_delta}}
