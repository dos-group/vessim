import pytest

from vessim.core.consumer import MockPowerMeter, ComputingSystem

class TestMockPowerMeter:

    @pytest.fixture
    def power_meter(self) -> MockPowerMeter:
        return MockPowerMeter(p=20, name="test")

    def test_initialize_fails_with_invalid_p_value(self):
        with pytest.raises(ValueError):
            MockPowerMeter(p=-1.0, name="test")

    def test_measure(self, power_meter):
        assert power_meter.measure() == 20.0
        power_meter.factor = 0.5
        assert power_meter.measure() == 10.0
        power_meter.factor = 0.25
        assert power_meter.measure() == 5.0


class TestComputingSystem:

    @pytest.fixture
    def computing_system(self) -> ComputingSystem:
        return ComputingSystem(
            power_meters=[
                MockPowerMeter(p=5, name="test1"), MockPowerMeter(p=7, name="test2")
            ],
            pue=1.5
        )

    def test_consumption(self, computing_system):
        assert computing_system.consumption() == 18.0

    def test_info(self, computing_system):
        assert computing_system.info() == {"test1": 5, "test2": 7}

    def test_finalize(self, computing_system):
        try:
            computing_system.finalize()
        except Exception as err:
            pytest.fail(f"Unexpected Error: {err}")
