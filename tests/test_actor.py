from datetime import timedelta
from unittest.mock import Mock

import pytest

from vessim.actor import Actor
from vessim.signal import Signal


class TestActor:
    @pytest.fixture
    def mock_signal(self):
        signal = Mock(spec=Signal)
        signal.at.return_value = 10.0
        signal.__str__ = Mock(return_value="MockSignal")
        return signal

    def test_init(self, mock_signal):
        actor = Actor(name="test_actor", signal=mock_signal, step_size=60)
        assert actor.name == "test_actor"
        assert actor.signal == mock_signal
        assert actor.step_size == 60

    def test_power(self, mock_signal):
        actor = Actor(name="test_actor", signal=mock_signal)
        elapsed = timedelta(hours=12)
        power = actor.power(elapsed)
        assert power == 10.0
        mock_signal.at.assert_called_once_with(elapsed)

    def test_state(self, mock_signal):
        actor = Actor(name="test_actor", signal=mock_signal)
        elapsed = timedelta(hours=12)
        state = actor.state(elapsed)
        assert state == {"power": 10.0}
        mock_signal.at.assert_called_once_with(elapsed)

    def test_consumer_negates_power(self, mock_signal):
        actor = Actor(name="test_actor", signal=mock_signal, consumer=True)
        assert actor.power(timedelta(hours=12)) == -10.0

    def test_consumer_false_by_default(self, mock_signal):
        actor = Actor(name="test_actor", signal=mock_signal)
        assert actor.consumer is False

    def test_finalize(self, mock_signal):
        actor = Actor(name="test_actor", signal=mock_signal)
        actor.finalize()
        mock_signal.finalize.assert_called_once()