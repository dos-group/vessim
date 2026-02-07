import pytest
from unittest.mock import Mock
from datetime import datetime
from vessim.actor import Actor
from vessim.signal import Signal

class TestActor:
    @pytest.fixture
    def mock_signal(self):
        signal = Mock(spec=Signal)
        signal.now.return_value = 10.0
        signal.__str__ = Mock(return_value="MockSignal")
        return signal

    def test_init(self, mock_signal):
        actor = Actor(name="test_actor", signal=mock_signal, step_size=60)
        assert actor.name == "test_actor"
        assert actor.signal == mock_signal
        assert actor.step_size == 60

    def test_power(self, mock_signal):
        actor = Actor(name="test_actor", signal=mock_signal)
        now = datetime(2023, 1, 1, 12, 0)
        power = actor.power(now)
        assert power == 10.0
        mock_signal.now.assert_called_once_with(at=now)

    def test_state(self, mock_signal):
        actor = Actor(name="test_actor", signal=mock_signal)
        now = datetime(2023, 1, 1, 12, 0)
        state = actor.state(now)
        assert state == {
            "name": "test_actor",
            "signal": "MockSignal",
            "power": 10.0,
        }
        mock_signal.now.assert_called_once_with(at=now)

    def test_finalize(self, mock_signal):
        actor = Actor(name="test_actor", signal=mock_signal)
        actor.finalize()
        mock_signal.finalize.assert_called_once()
