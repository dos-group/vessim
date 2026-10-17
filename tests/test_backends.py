"""Behavioral contracts shared by native and mosaik execution."""

import importlib.util
from datetime import timedelta
import json
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

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
    from benchmarks.run import build, digest

    fixture = Path(__file__).parents[1] / "benchmarks/input.csv"
    traces = {c: vs.Trace.from_csv(fixture, column=c) for c in ("solar", "load", "carbon")}
    baseline = json.loads((Path(__file__).parents[1] / "benchmarks/baseline.json").read_text())
    expected = baseline["cases"][case]
    env, memory = build(backend, case, traces, tmp_path / "output")
    result = env.run(expected["steps"] * 60)
    assert result.steps == expected["steps"]
    legacy_log = {
        now: {
            name: {
                **state,
                "policy_state": {"mode": "grid-connected", **state["policy_state"]},
                "dispatch_states": {
                    k: v for k, v in state["dispatch_states"].items() if k != "grid"
                },
            }
            for name, state in states.items()
        }
        for now, states in memory.log.items()
    }
    assert digest(SimpleNamespace(log=legacy_log)) == expected["trajectory_sha256"]


@pytest.mark.parametrize("horizon", [0, 0.5, 1, 2, 2.5])
def test_boundaries_with_explicit_grid(backend, horizon):
    env = vs.Environment("2026-01-01", backend=backend)
    env.add_microgrid(
        [vs.Actor("a.with.dots", 1)],
        name="grid.with.dots",
        dispatchables=[vs.GridConnection()],
    )
    log = env.add_controller(vs.Recorder(metrics=False))
    result = env.run(horizon)
    assert result.steps == len(range(0, int(np.ceil(horizon))))
    assert all(
        state["grid.with.dots"]["dispatch_states"]
        == {"grid": {"current_power": 1, "connected": True}}
        for state in log.log.values()
    )


@pytest.mark.parametrize("failure", [RuntimeError("test failure"), KeyboardInterrupt()])
def test_step_failure_cleanup(backend, failure):
    closed = []

    class Signal(vs.Signal):
        def __init__(self, value):
            self.value = value

        def at(self, elapsed):
            return self.value

        def finalize(self):
            closed.append("signal")

    env = vs.Environment("2026-01-01", backend=backend)
    env.add_microgrid(
        [vs.Actor("a", Signal(1))],
        grid_signals={"x": Signal(2)},
        dispatchables=[vs.GridConnection()],
    )
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
    env.add_microgrid([vs.Actor("a", 1)], dispatchables=[vs.GridConnection()])
    env.add_controller(Broken(events))
    unstarted = env.add_controller(Record())
    with pytest.raises(ValueError, match="start failed"):
        env.run(1)
    assert events == ["start", "finalize"]
    assert unstarted.events == []
    assert env._closed


def test_sampling_feedback_and_integration_order(backend):
    samples = []

    class Actor(vs.Actor):
        def sample(self, elapsed):
            samples.append(elapsed)
            return super().sample(elapsed)

    actor = Actor("a", power=100, step_size=120)
    battery = vs.SimpleBattery("battery", 100, initial_soc=0.5)

    class Feedback(vs.Controller):
        def step(self, now, states):
            actor.power = 200

    env = vs.Environment("2026-01-01", step_size=60, backend=backend)
    env.add_microgrid([actor], [battery, vs.GridConnection()], name="grid")
    env.add_controller(Feedback())
    log = env.add_controller(vs.Recorder(metrics=False))
    env.run(180)
    rows = [row["grid"] for row in log.log.values()]
    assert samples == [0, 120]  # One read per actor update.
    assert [row["p_delta"] for row in rows] == [100, 100, 200]
    assert rows[0]["dispatch_states"]["battery"]["soc"] == 0.5
    assert battery.charge_level == pytest.approx(50 + (2 * 100 + 200) / 60)


def test_live_wall_clock_pacing(backend):
    timestamps = []

    class Observe(vs.Controller):
        def step(self, now, states):
            timestamps.append(time.monotonic())

    env = vs.Environment.live(backend=backend)
    env.add_microgrid([vs.Actor("a", 1)], dispatchables=[vs.GridConnection()])
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
e.add_microgrid([vs.Actor('a',1)], [vs.GridConnection()])
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
    env.add_microgrid([vs.Actor("a", 1)], dispatchables=[vs.GridConnection()])
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
        def sample(self, elapsed):
            power, state = super().sample(elapsed)
            return power, {**state, "temperature": [20 + elapsed]}

    env = vs.Environment("2026-01-01", step_size=60, backend=backend)
    device = Device()
    env.add_microgrid([Actor("a", 100)], [device, vs.GridConnection()], name="grid")
    log = env.add_controller(vs.Recorder(metrics=False))
    result = env.run(120)
    rows = list(log.log.values())
    assert rows[0]["grid"]["dispatch_states"]["device"]["nested"]["energy"] == 0
    assert device.energy == pytest.approx(2 * 50 / 60)
    assert rows[1]["grid"]["actor_states"]["a"]["temperature"] == [80]
    result.states["grid"]["actor_states"]["a"]["temperature"][0] = 999
    assert rows[1]["grid"]["actor_states"]["a"]["temperature"] == [80]


@pytest.mark.parametrize("horizon", [0, 0.5, 30, 60, 90, 120, 150.5])
@pytest.mark.parametrize("record", [False, True])
def test_final_state_covers_the_exact_horizon(backend, horizon, record):
    env = vs.Environment("2026-01-01", step_size=60, backend=backend)
    battery = vs.SimpleBattery("battery", capacity=2, initial_soc=1)
    env.add_microgrid([vs.Actor("load", -60)], [battery, vs.GridConnection()], name="site")
    rec = env.add_controller(vs.Recorder()) if record else None
    result = env.run(horizon)
    discharged = min(2, horizon / 60)
    assert battery.charge_level == pytest.approx(2 - discharged)
    if horizon:
        assert result.states["site"]["dispatch_states"]["battery"]["charge_level"] == (
            pytest.approx(battery.charge_level)
        )
        if rec:
            metrics = rec.metrics["microgrids"]["site"]
            assert metrics["energy_consumed"] == pytest.approx(horizon / 60)
            assert metrics["grid_import"] + discharged == pytest.approx(horizon / 60)
            assert len(rec.log) == int(np.ceil(horizon / 60))
            assert (max(rec.log) - env.sim_start).total_seconds() < horizon
    else:
        assert result.states == {}


def test_final_partial_interval_uses_remaining_battery_energy(backend):
    env = vs.Environment("2026-01-01", step_size=60, backend=backend)
    battery = vs.SimpleBattery("battery", capacity=1.5, initial_soc=1)
    # A pre-existing setpoint must not consume energy before time zero.
    battery.set_power(-60, 60)
    env.add_microgrid([vs.Actor("load", -60)], [battery, vs.GridConnection()], name="site")
    rec = env.add_controller(vs.Recorder())
    result = env.run(90)
    rows = list(rec.log.values())
    assert rows[0]["site"]["dispatch_states"]["battery"]["charge_level"] == 1.5
    assert rows[1]["site"]["dispatch_states"]["battery"]["charge_level"] == 0.5
    assert rows[1]["site"]["p_grid"] == 0  # 0.5 Wh covers the remaining 30 s.
    assert rec.metrics["microgrids"]["site"]["grid_import"] == 0
    assert result.states["site"]["dispatch_states"]["battery"]["charge_level"] == 0
    assert result.last_time == env.sim_start + timedelta(seconds=60)


def test_clc_dispatch_respects_energy_available_above_min_soc(backend):
    env = vs.Environment("2026-01-01", step_size=3600, backend=backend)
    battery = vs.ClcBattery(
        "battery",
        initial_soc=1,
        min_soc=0.2,
        v_2=10,
        u_1=0,
        u_2=0,
        eta_d=1,
        eta_c=1,
        alpha_d=-10,
    )
    env.add_microgrid([vs.Actor("load", -10)], [battery, vs.GridConnection()], name="site")
    rec = env.add_controller(vs.Recorder(timeseries=False))
    env.run(3600)
    assert battery.charge_level == pytest.approx(2)
    assert rec.metrics["microgrids"]["site"]["grid_import"] == pytest.approx(2)


@pytest.mark.parametrize("actor_period", [60, 120])
def test_demand_response_changes_only_future_samples(backend, actor_period):
    datacenter = vs.Consumer("dc", power=1000, step_size=actor_period)

    class DemandResponse(vs.Controller):
        def step(self, now, states):
            datacenter.power = 700

    env = vs.Environment("2026-01-01", step_size=60, backend=backend)
    env.add_microgrid([datacenter], [vs.GridConnection()], name="site")
    env.add_controller(DemandResponse())
    recorder = env.add_controller(vs.Recorder())
    env.run(180)
    expected = [-1000, -700 if actor_period == 60 else -1000, -700]
    rows = [states["site"] for states in recorder.log.values()]
    assert [row["actor_states"]["dc"]["power"] for row in rows] == expected
    assert [row["p_delta"] for row in rows] == expected
    assert [row["p_grid"] for row in rows] == expected
    assert recorder.metrics["actors"]["site"]["dc"]["energy_consumed"] == pytest.approx(
        -sum(expected) / 60
    )
    config = recorder.result.config["microgrids"]["site"]["actors"][0]
    assert config["type"] == "Consumer"
    assert config["power"] == 1000


def test_shared_and_replaced_signal_lifecycle(backend):
    events = []

    class Input(vs.Signal):
        def __init__(self, name, value):
            self.name = name
            self.value = value

        def start(self):
            events.append((self.name, "start"))

        def at(self, elapsed):
            assert (self.name, "start") in events
            return self.value

        def finalize(self):
            events.append((self.name, "close"))

    first = Input("first", 10)
    second = Input("second", 20)
    load = vs.Consumer("load", power=first)
    solar = vs.Producer("solar", power=first)
    env = vs.Environment("2026-01-01", backend=backend)
    grid = env.add_microgrid(
        [load, solar], [vs.GridConnection()], grid_signals={"context": first}, name="site"
    )
    assert events == []

    class Replace(vs.Controller):
        def step(self, now, states):
            load.power = second
            solar.power = 0
            grid.grid_signals["context"] = 0.25

    env.add_controller(Replace())
    rec = env.add_controller(vs.Recorder())
    env.run(2)
    env.close()
    assert events == [
        ("first", "start"),
        ("second", "start"),
        ("first", "close"),
        ("second", "close"),
    ]
    assert [s["site"]["p_delta"] for s in rec.log.values()] == [0, -20]
    assert [s["site"]["grid_signals"]["context"] for s in rec.log.values()] == [10, 0.25]


def test_signal_start_failure_closes_all_inputs(backend):
    events = []

    class Input(vs.Signal):
        def __init__(self, name, fail=False):
            self.name = name
            self.fail = fail

        def start(self):
            events.append((self.name, "start"))
            if self.fail:
                raise RuntimeError("input startup failed")

        def at(self, elapsed):
            raise AssertionError("Failed setup must not sample inputs")

        def finalize(self):
            events.append((self.name, "close"))

    env = vs.Environment("2026-01-01", backend=backend)
    env.add_microgrid(
        [vs.Consumer("load", power=Input("load", fail=True))],
        [vs.GridConnection()],
        grid_signals={"price": Input("price")},
    )
    with pytest.raises(RuntimeError, match="input startup failed"):
        env.run(1)
    env.close()
    assert events == [("load", "start"), ("load", "close"), ("price", "close")]
