from datetime import timedelta
from unittest.mock import Mock

import pytest

import vessim as vs


@pytest.mark.parametrize(
    "actor_type, value, expected",
    [
        (vs.Actor, -700, -700),
        (vs.Actor, 700, 700),
        (vs.Consumer, 700, -700),
        (vs.Producer, 700, 700),
        (vs.Consumer, 0, 0),
        (vs.Producer, 0, 0),
    ],
)
@pytest.mark.parametrize("use_signal", [False, True])
def test_power_convention_and_single_sample(actor_type, value, expected, use_signal):
    signal = Mock(spec=vs.Signal)
    signal.at.return_value = value
    actor = actor_type("device", signal=signal if use_signal else value, step_size=60)
    elapsed = timedelta(hours=1)
    assert actor.sample(elapsed) == (expected, {"power": expected})
    if use_signal:
        signal.at.assert_called_once_with(elapsed)
    assert actor.step_size == 60


@pytest.mark.parametrize("actor_type", [vs.Actor, vs.Consumer, vs.Producer])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, "700", lambda t: 700])
def test_invalid_constant_rejected_without_changing_input(actor_type, value):
    with pytest.raises(ValueError, match="finite number"):
        actor_type("invalid", signal=value)
    actor = actor_type("device", signal=700)
    with pytest.raises(ValueError, match="finite number"):
        actor.signal = value
    assert isinstance(actor.signal, vs.StaticSignal)
    assert actor.signal.at() == 700


@pytest.mark.parametrize("actor_type", [vs.Consumer, vs.Producer])
def test_negative_magnitude_rejected_at_assignment_and_sampling(actor_type):
    with pytest.raises(ValueError, match="nonnegative"):
        actor_type("device", signal=-1)
    actor = actor_type("device", signal=700)
    with pytest.raises(ValueError, match="nonnegative"):
        actor.signal = -1
    assert isinstance(actor.signal, vs.StaticSignal)
    assert actor.signal.at() == 700
    signal = Mock(spec=vs.Signal)
    signal.at.side_effect = [1, -1]
    actor.signal = signal
    actor.sample(0)
    with pytest.raises(ValueError, match="nonnegative"):
        actor.sample(1)


def test_signed_actor_can_change_direction():
    signal = Mock(spec=vs.Signal)
    signal.at.side_effect = [-700, 200]
    actor = vs.Actor("net_meter", signal=signal)
    assert actor.sample(0)[0] == -700
    assert actor.sample(1)[0] == 200


def test_custom_actor_extends_one_sample_with_diagnostics():
    signal = Mock(spec=vs.Signal)
    signal.at.side_effect = [700, 800]

    class Datacenter(vs.Consumer):
        def sample(self, elapsed):
            power, state = super().sample(elapsed)
            return power, {**state, "active_jobs": 3}

    actor = Datacenter("dc", signal=signal)
    assert actor.sample(0) == (-700, {"power": -700, "active_jobs": 3})
    signal.at.assert_called_once_with(0)


def test_constant_update_and_configuration():
    actor = vs.Consumer("load", signal=700)
    assert actor.config() == {
        "name": "load",
        "type": "Consumer",
        "signal": "StaticSignal(700)",
        "step_size": None,
    }
    actor.signal = 1200
    assert actor.sample(60) == (-1200, {"power": -1200})


def test_numeric_assignment_replaces_shared_signal_without_changing_other_actor():
    signal = vs.StaticSignal(700)
    first = vs.Consumer("first", signal=signal)
    second = vs.Consumer("second", signal=signal)
    assert first.signal is second.signal is signal
    first.signal = 500
    assert first.signal is not signal
    assert isinstance(first.signal, vs.StaticSignal)
    assert first.sample(0)[0] == -500
    assert second.sample(0)[0] == -700


@pytest.mark.parametrize("kind", [vs.Consumer, vs.Producer])
def test_explicit_constant_validated_on_assignment_and_after_mutation(kind):
    with pytest.raises(ValueError, match="nonnegative"):
        kind("device", signal=vs.StaticSignal(-1))
    signal = vs.StaticSignal(700)
    actor = kind("device", signal=signal)
    signal.set_value(-1)
    with pytest.raises(ValueError, match="nonnegative"):
        actor.sample(0)
