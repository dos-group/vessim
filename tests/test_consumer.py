import pytest
from datetime import datetime

import vessim as vs


class TestComputingSystem:
    @pytest.fixture
    def computing_system(self) -> vs.ComputingSystem:
        return vs.ComputingSystem(
            name="test_comp",
            step_size=60,
            power_meters=[
                vs.MockPowerMeter(name="test1", p=5.0),
                vs.MockPowerMeter(name="test2", p=7.0),
            ],
            pue=1.5,
        )

    def test_p(self, computing_system):
        assert computing_system.p(datetime.now()) == -18.0

    def test_state(self, computing_system):
        assert computing_system.state(datetime.now()) == {
            "p": -18.0,
            "power_meters": {"test1": -5.0, "test2": -7.0},
        }
