import pytest
from datetime import datetime

import vessim as vs


class TestComputingSystem:
    @pytest.fixture
    def computing_system(self) -> vs.ComputingSystem:
        return vs.ComputingSystem(
            name="test_comp",
            step_size=60,
            nodes=[
                vs.MockSignal(name="test1", value=5.0),
                vs.MockSignal(name="test2", value=7.0),
            ],
            pue=1.5,
        )

    def test_p(self, computing_system):
        assert computing_system.p(datetime.now()) == -18.0

    def test_state(self, computing_system):
        assert computing_system.state(datetime.now()) == {
            "p": -18.0,
            "nodes": {"test1": -5.0, "test2": -7.0},
        }
