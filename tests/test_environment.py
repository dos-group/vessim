import pytest
from unittest.mock import Mock, patch
from datetime import datetime
import vessim.environment
from vessim.environment import Environment
from vessim.actor import Actor
from vessim.signal import Signal, SilSignal
from vessim.microgrid import Microgrid

class TestEnvironment:
    @pytest.fixture
    def mock_mosaik_world(self):
        with patch("vessim.environment.mosaik.World") as mock_world:
            yield mock_world

    @pytest.fixture
    def environment(self, mock_mosaik_world):
        return Environment(sim_start="2023-01-01 00:00:00")

    def test_init(self, mock_mosaik_world):
        env = Environment(sim_start="2023-01-01 00:00:00", step_size=60)
        assert env.step_size == 60
        assert env.microgrids == []
        assert env.controllers == []
        mock_mosaik_world.assert_called_once()

    def test_add_microgrid_raises_no_actors(self, environment):
        with pytest.raises(ValueError, match="There should be at least one actor"):
            environment.add_microgrid(actors=[])

    def test_add_microgrid(self, environment):
        mock_actor = Mock(spec=Actor)
        mock_actor.step_size = None
        mock_actor.name = "test_actor"
        
        # We need to patch Microgrid init because it interacts with mosaik world
        with patch("vessim.environment.Microgrid") as mock_microgrid_cls:
            mg_instance = mock_microgrid_cls.return_value
            mg = environment.add_microgrid(actors=[mock_actor])
            
            assert mg == mg_instance
            assert mg in environment.microgrids
            mock_microgrid_cls.assert_called_once()

    def test_run_validates_sil_signals(self, environment):
        class DummySilSignal(SilSignal):
            def __init__(self): pass
            def _fetch_current_value(self): return 0
            def finalize(self): pass

        # Create a mock microgrid with a mock actor having a SilSignal
        mock_actor = Mock(spec=Actor)
        mock_actor.signal = DummySilSignal()
        
        # We can't easily mock the internal state of Environment without adding a microgrid.
        # So we add a mocked microgrid.
        
        mg = Mock(spec=Microgrid)
        mg.actors = [mock_actor]
        environment.microgrids = [mg]
        
        # Should raise RuntimeError if rt_factor is None
        with pytest.raises(RuntimeError, match="SiL actors detected"):
            environment.run(until=100)

    def test_contains_sil_signals(self, environment):
        mg = Mock(spec=Microgrid)
        actor1 = Mock(spec=Actor)
        actor1.signal = Mock(spec=Signal) # Not SilSignal
        
        actor2 = Mock(spec=Actor)
        
        class DummySilSignal(SilSignal):
            def __init__(self): pass
            def _fetch_current_value(self): return 0
            def finalize(self): pass
            
        actor2.signal = DummySilSignal()
        
        mg.actors = [actor1, actor2]
        environment.microgrids = [mg]
        
        assert environment._contains_sil_signals() is True
        
        # Check negative case
        mg.actors = [actor1]
        assert environment._contains_sil_signals() is False

