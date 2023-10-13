import pytest

from vessim.core.consumer import MockPowerMeter, ComputingSystem


class TestMockPowerMeter:
    @pytest.fixture
    def power_meter(self) -> MockPowerMeter:
        return MockPowerMeter(name="test", p=20)

    def test_initialize_fails_with_invalid_p_value(self):
        with pytest.raises(ValueError):
            MockPowerMeter(name="test", p=-1.0)

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
                MockPowerMeter(name="test1", p=5),
                MockPowerMeter(name="test2", p=7),
            ],
            pue=1.5,
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
