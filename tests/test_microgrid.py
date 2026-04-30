import pytest
from unittest.mock import Mock
from vessim.microgrid import Microgrid
from vessim.actor import Actor
from vessim.dispatch_policy import DispatchPolicy

class TestMicrogrid:
    @pytest.fixture
    def mock_world(self):
        return Mock()

    @pytest.fixture
    def mock_policy(self):
        return Mock(spec=DispatchPolicy)

    def test_init_raises_invalid_step_size(self, mock_world, mock_policy):
        actor = Mock(spec=Actor)
        actor.step_size = 10
        actor.name = "test_actor"

        with pytest.raises(ValueError, match="Actor step size has to be a multiple"):
            Microgrid(
                world=mock_world,
                step_size=3,
                actors=[actor],
                dispatchables=[],
                policy=mock_policy
            )

    def test_init_connects_components(self, mock_world, mock_policy):
        actor = Mock(spec=Actor)
        actor.step_size = 10
        actor.name = "test_actor"

        # Setup mocks for world.start() returns
        actor_sim = Mock()
        microgrid_sim = Mock()

        mock_world.start.side_effect = [actor_sim, microgrid_sim]

        actor_entity = Mock()
        actor_sim.Actor.return_value = actor_entity

        microgrid_entity = Mock()
        microgrid_sim.Microgrid.return_value = microgrid_entity

        mg = Microgrid(
            world=mock_world,
            step_size=5,  # 10 % 5 == 0
            actors=[actor],
            dispatchables=[],
            policy=mock_policy,
        )

        # Check if actors are started
        mock_world.start.assert_any_call("Actor", sim_id=f"{mg.name}.actor.test_actor",
                                         step_size=10)

        # Check if microgrid sim is started
        mock_world.start.assert_any_call("Microgrid", sim_id=f"{mg.name}.microgrid",
                                         step_size=5, grid_signals=None)

        # Check connections
        mock_world.connect.assert_any_call(actor_entity, microgrid_entity, "power")

    def test_finalize(self, mock_world, mock_policy):
        actor = Mock(spec=Actor)
        actor.step_size = 5
        actor.name = "test_actor"

        # Simplify world mock for this test
        mock_world.start.return_value = Mock()

        mg = Microgrid(
            world=mock_world,
            step_size=5,
            actors=[actor],
            dispatchables=[],
            policy=mock_policy
        )

        mg.finalize()
        actor.finalize.assert_called_once()
