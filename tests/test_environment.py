from datetime import datetime, timedelta
import math

import pytest

import vessim as vs


def environment(**kwargs):
    env = vs.Environment(sim_start="2026-01-01", **kwargs)
    env.add_microgrid([vs.Actor("load", vs.StaticSignal(-100))])
    return env


@pytest.mark.parametrize("step_size", [0, -1, 1.5, True])
def test_invalid_step_size(step_size):
    with pytest.raises(ValueError, match="positive integer"):
        environment(step_size=step_size)


def test_backend_validation():
    with pytest.raises(ValueError, match="backend"):
        environment(backend="unknown")
    with pytest.raises(ValueError, match="requires"):
        environment(sim_config={})
    env = environment()
    with pytest.raises(RuntimeError, match="mosaik"):
        _ = env.world


def test_native_setup_and_freeze():
    env = environment()
    assert env.status == "created"
    assert list(env.microgrids) == ["microgrid_0"]
    env.prepare()
    with pytest.raises(RuntimeError, match="frozen"):
        env.add_controller(vs.Recorder(metrics=False))
    env.close()
    with pytest.raises(RuntimeError, match="once"):
        env.run(until=1)


@pytest.mark.parametrize(
    "until, count",
    [
        (0, 0),
        (1, 1),
        (2, 2),
        (2.5, 3),
        (timedelta(seconds=2), 2),
        (datetime(2026, 1, 1, 0, 0, 2), 2),
    ],
)
def test_exclusive_end(until, count):
    env = environment()
    result = env.run(until)
    assert result.steps == count
    assert env.status == "completed"
    assert (result.last_time is None) == (count == 0)
    with pytest.raises(RuntimeError, match="once"):
        env.run(until)


@pytest.mark.parametrize("until", [None, -1, math.nan, math.inf, True, "1"])
def test_invalid_end(until):
    env = environment()
    with pytest.raises((ValueError, TypeError)):
        env.run(until)
    assert env.status == "failed"
    assert env._closed


def test_duplicate_names_and_models():
    env = environment()
    with pytest.raises(ValueError, match="already exists"):
        env.add_microgrid([vs.Actor("x", vs.StaticSignal(1))], name="microgrid_0")
    actor = env.microgrids["microgrid_0"].actors[0]
    env.add_microgrid([actor])
    with pytest.raises(ValueError, match="cannot be shared"):
        env.run(1)


def test_grid_live_signal_is_validated_and_closed():
    class Live(vs.SilSignal):
        def __init__(self):
            self.closed = False

        def _fetch_current_value(self):
            return 0

        def finalize(self):
            self.closed = True

    signal = Live()
    env = vs.Environment(sim_start="2026-01-01")
    env.add_microgrid([vs.Actor("a", vs.StaticSignal(0))], grid_signals={"live": signal})
    with pytest.raises(RuntimeError, match="SiL signals"):
        env.run(1)
    assert signal.closed


def test_actor_sampling_interval_rejected():
    env = vs.Environment(sim_start="2026-01-01", step_size=3)
    with pytest.raises(ValueError, match="positive multiple"):
        env.add_microgrid([vs.Actor("a", vs.StaticSignal(1), step_size=2)])


def test_prepare_captures_actor_configuration():
    class CountingSignal(vs.StaticSignal):
        def at(self, elapsed):
            calls.append(elapsed)
            return super().at(elapsed)

    calls = []
    env = vs.Environment(sim_start="2026-01-01")
    actor = vs.Actor("old_name", CountingSignal(1))
    env.add_microgrid([actor])
    actor.name = "new_name"
    actor.step_size = 2
    result = env.run(4)
    assert calls == [0, 2]
    assert list(result.states["microgrid_0"]["actor_states"]) == ["new_name"]
