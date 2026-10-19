"""Small independent mosaik simulator, also runnable as an external process."""
from pathlib import Path
import mosaik_api_v3


class PowerSource(mosaik_api_v3.Simulator):
    def __init__(self):
        super().__init__({"type": "time-based", "models": {
            "Source": {"public": True, "params": [], "attrs": ["power", "feedback"]},
        }})
        self.value = 100
        self.period = 1
        self.marker = None
        self.records = None
        self.failure = False

    def init(self, sid, time_resolution=1.0, **params):
        self.period = params.get("period", 1)
        self.marker = params.get("marker")
        self.records = params.get("records")
        self.failure = params.get("failure", False)
        return self.meta

    def create(self, num, model):
        return [{"eid": str(i), "type": model} for i in range(num)]

    def step(self, time, inputs, max_advance):
        if self.failure and time == 1:
            raise RuntimeError("external failure")
        feedback = sum(inputs.get("0", {}).get("feedback", {}).values())
        self.value = 100 + time + feedback
        if self.records is not None:
            self.records.append((time, feedback))
        return time + self.period

    def get_data(self, outputs):
        return {eid: {attr: self.value for attr in attrs} for eid, attrs in outputs.items()}

    def finalize(self):
        if self.marker:
            Path(self.marker).write_text("finalized")


if __name__ == "__main__":
    mosaik_api_v3.start_simulation(PowerSource())
