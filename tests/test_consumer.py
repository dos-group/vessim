import pytest
from datetime import datetime

from vessim.cosim import MockPowerMeter, ComputingSystem


class TestComputingSystem:
    @pytest.fixture
    def computing_system(self) -> ComputingSystem:
        return ComputingSystem(
            name="test_comp",
            step_size=60,
            power_meters=[
                MockPowerMeter(name="test1", p=5.0),
                MockPowerMeter(name="test2", p=7.0),
            ],
            pue=1.5,
        )

    def test_p(self, computing_system):
        assert computing_system.p(datetime.now()) == -18.0

    def test_info(self, computing_system):
        assert computing_system.info(datetime.now()) == {"test1": -5.0, "test2": -7.0}
