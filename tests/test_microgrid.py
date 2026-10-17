import pytest

import vessim as vs


def test_model_construction_has_no_backend():
    grid = vs.Microgrid(
        step_size=60,
        actors=[vs.Actor("a", vs.StaticSignal(100))],
        dispatchables=[vs.GridConnection()],
        policy=vs.DefaultDispatchPolicy(),
    )
    assert not hasattr(grid, "world")
    grid.sample(0)
    grid.advance(0)
    assert grid.state()["p_grid"] == 100
    assert grid.state()["dispatch_states"] == {"grid": {"current_power": 100, "connected": True}}


def test_duplicate_actor_names_rejected():
    with pytest.raises(ValueError, match="unique"):
        vs.Microgrid(
            1,
            [vs.Actor("a", vs.StaticSignal(0)), vs.Actor("a", vs.StaticSignal(1))],
            [],
            vs.DefaultDispatchPolicy(),
        )


def test_state_is_detached_from_mutable_custom_actor():
    class Stateful(vs.Actor):
        data = {"nested": {"value": 1}}

        def state(self, elapsed):
            return self.data

    actor = Stateful("a", vs.StaticSignal(0))
    grid = vs.Microgrid(1, [actor], [], vs.DefaultDispatchPolicy())
    grid.sample(0)
    grid.advance(0)
    state = grid.state()
    actor.data["nested"]["value"] = 2
    assert state["actor_states"]["a"]["nested"]["value"] == 1
    state["actor_states"]["a"]["nested"]["value"] = 3
    assert actor.data["nested"]["value"] == 2


def test_custom_scalar_subclass_state_is_copied():
    class Scalar(float):
        pass

    value = Scalar(1)
    value.history = [1]

    class Actor(vs.Actor):
        def state(self, elapsed):
            return {"value": value}

    grid = vs.Microgrid(1, [Actor("a", vs.StaticSignal(0))], [], vs.DefaultDispatchPolicy())
    grid.sample(0)
    snapshot = grid.state()
    value.history.append(2)
    assert snapshot["actor_states"]["a"]["value"].history == [1]
