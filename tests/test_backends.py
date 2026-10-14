"""Behavioral contracts shared by native and mosaik execution."""

import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest

import vessim as vs

HAS_MOSAIK = importlib.util.find_spec("mosaik") is not None
BACKENDS = [
    "native",
    pytest.param(
        "mosaik",
        marks=pytest.mark.skipif(not HAS_MOSAIK, reason="optional mosaik extra not installed"),
    ),
]


@pytest.fixture(params=BACKENDS)
def backend(request):
    return request.param


class Record(vs.Controller):
    def __init__(self, event=None, failure=None):
        self.events = event if event is not None else []
        self.failure = failure

    def start(self, env):
        self.events.append("start")

    def step(self, now, states):
        self.events.append("step")
        if self.failure:
            raise self.failure

    def finalize(self):
        self.events.append("finalize")


@pytest.mark.parametrize(
    "case", ["static", "traces", "csv", "many_grids", "mixed_rates", "feedback"]
)
def test_pre_refactor_trajectory(backend, case, tmp_path):
    # The checksum fixture was recorded against cd417e18 before changing the
    # engine. This catches shared mistakes that backend-to-backend tests cannot.
    from benchmarks.run import build, digest

    fixture = Path(__file__).parents[1] / "benchmarks/input.csv"
    traces = {c: vs.Trace.from_csv(fixture, column=c) for c in ("solar", "load", "carbon")}
    baseline = json.loads((Path(__file__).parents[1] / "benchmarks/baseline.json").read_text())
    expected = baseline["cases"][case]
    env, memory = build(backend, case, traces, tmp_path / "output")
    result = env.run(expected["steps"] * 60)
    assert result.steps == expected["steps"]
    assert digest(memory) == expected["trajectory_sha256"]


@pytest.mark.parametrize("horizon", [0, 0.5, 1, 2, 2.5])
def test_boundaries_and_empty_dispatchables(backend, horizon):
    env = vs.Environment("2026-01-01", backend=backend)
    env.add_microgrid([vs.Actor("a.with.dots", vs.StaticSignal(1))], name="grid.with.dots")
    log = env.add_controller(vs.MemoryLogger())
    result = env.run(horizon)
    assert result.steps == len(range(0, int(np.ceil(horizon))))
    assert all(state["grid.with.dots"]["dispatch_states"] == {} for state in log.log.values())


@pytest.mark.parametrize("failure", [RuntimeError("test failure"), KeyboardInterrupt()])
def test_step_failure_cleanup(backend, failure):
    closed = []

    class Signal(vs.StaticSignal):
        def finalize(self):
            closed.append("signal")

    env = vs.Environment("2026-01-01", backend=backend)
    env.add_microgrid([vs.Actor("a", Signal(1))], grid_signals={"x": Signal(2)})
    record = env.add_controller(Record(failure=failure))
    with pytest.raises(type(failure)):
        env.run(3)
    assert record.events == ["start", "step", "finalize"]
    assert closed == ["signal", "signal"]
    assert env.status == ("interrupted" if isinstance(failure, KeyboardInterrupt) else "failed")
    env.close()
    assert len(closed) == 2


def test_partial_initialization_and_cleanup_errors(backend):
    events = []

    class Broken(Record):
        def start(self, env):
            super().start(env)
            raise ValueError("start failed")

        def finalize(self):
            super().finalize()
            raise RuntimeError("cleanup failed")

    env = vs.Environment("2026-01-01", backend=backend)
    env.add_microgrid([vs.Actor("a", vs.StaticSignal(1))])
    env.add_controller(Broken(events))
    unstarted = env.add_controller(Record())
    with pytest.raises(ValueError, match="start failed"):
        env.run(1)
    assert events == ["start", "finalize"]
    assert unstarted.events == []
    assert env._closed


def test_sampling_feedback_and_integration_order(backend):
    samples = []

    class Signal(vs.StaticSignal):
        def at(self, elapsed=None):
            samples.append(elapsed)
            return super().at(elapsed)

    signal = Signal(100)
    battery = vs.SimpleBattery("battery", 100, initial_soc=0.5)

    class Feedback(vs.Controller):
        def step(self, now, states):
            signal.set_value(200)

    env = vs.Environment("2026-01-01", step_size=60, backend=backend)
    env.add_microgrid([vs.Actor("a", signal, step_size=120)], [battery], name="grid")
    env.add_controller(Feedback())
    log = env.add_controller(vs.MemoryLogger())
    env.run(180)
    rows = [row["grid"] for row in log.log.values()]
    assert samples == [0, 120]  # One read per actor update.
    assert [row["p_delta"] for row in rows] == [100, 100, 200]
    assert rows[0]["dispatch_states"]["battery"]["soc"] == 0.5
    assert battery.charge_level == pytest.approx(50 + 2 * 100 / 60)


def test_live_wall_clock_pacing(backend):
    timestamps = []

    class Observe(vs.Controller):
        def step(self, now, states):
            timestamps.append(time.monotonic())

    env = vs.Environment.live(backend=backend)
    env.add_microgrid([vs.Actor("a", vs.StaticSignal(1))])
    env.add_controller(Observe())
    t0 = time.monotonic()
    env.run(1.05)
    assert len(timestamps) == 2
    assert timestamps[1] - timestamps[0] >= 0.9
    assert time.monotonic() - t0 >= 1.0


def test_native_import_does_not_require_mosaik():
    source = """
import sys
class BlockMosaik:
    def find_spec(self, fullname, *args):
        if fullname.startswith('mosaik'):
            raise ImportError('blocked optional dependency')
sys.meta_path.insert(0, BlockMosaik())
import vessim as vs
e = vs.Environment('2026-01-01')
e.add_microgrid([vs.Actor('a',vs.StaticSignal(1))])
assert e.run(2).steps == 2
assert not any(n.startswith('mosaik') for n in sys.modules)
try:
    vs.Environment('2026-01-01', backend='mosaik').world
except ImportError as exc:
    assert 'vessim[mosaik]' in str(exc)
else:
    raise AssertionError('expected missing-extra error')
"""
    subprocess.run([sys.executable, "-c", source], check=True, capture_output=True, text=True)


def test_unbounded_live_interrupt(backend):
    env = vs.Environment.live(backend=backend)
    env.add_microgrid([vs.Actor("a", vs.StaticSignal(1))])
    record = env.add_controller(Record(failure=KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        env.run()
    assert record.events == ["start", "step", "finalize"]
    assert env.status == "interrupted"


def test_custom_actor_and_dispatchable_extensions(backend):
    class Device(vs.Dispatchable):
        def __init__(self):
            super().__init__("device")
            self.energy = 0.0

        def feasible_range(self, duration):
            return -50, 50

        def step(self, duration):
            self.energy += self.current_power * duration / 3600

        def state(self):
            return {"nested": {"energy": self.energy}}

        def config(self):
            return {}

    class Actor(vs.Actor):
        def state(self, elapsed):
            return {"power": self.power(elapsed), "temperature": [20 + elapsed]}

    env = vs.Environment("2026-01-01", step_size=60, backend=backend)
    device = Device()
    env.add_microgrid([Actor("a", vs.StaticSignal(100))], [device], name="grid")
    log = env.add_controller(vs.MemoryLogger())
    result = env.run(120)
    rows = list(log.log.values())
    assert rows[0]["grid"]["dispatch_states"]["device"]["nested"]["energy"] == 0
    assert device.energy == pytest.approx(50 / 60)
    assert rows[1]["grid"]["actor_states"]["a"]["temperature"] == [80]
    result.states["grid"]["actor_states"]["a"]["temperature"][0] = 999
    assert rows[1]["grid"]["actor_states"]["a"]["temperature"] == [80]
