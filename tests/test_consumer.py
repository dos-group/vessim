import pytest

from vessim.core.consumer import MockPowerMeter, ComputingSystem

class TestMockPowerMeter:

    @pytest.fixture
    def power_meter(self) -> MockPowerMeter:
        return MockPowerMeter(p=20, power_config={
            "high performance": 1,
            "normal": .8,
            "power-saving": .4
        })

    def test_initialize_fails_with_invalid_p_value(self):
        with pytest.raises(ValueError):
            MockPowerMeter(p=-1.0)

    def test_initialize_fails_with_invalid_power_config(self):
        with pytest.raises(ValueError):
            MockPowerMeter(p=10, power_config={
                "high performance": 1,
                "normal": .7
            })
        with pytest.raises(ValueError):
            MockPowerMeter(p=10, power_config={
                "invalid_mode": 1,
                "normal": .7,
                "power-saving": 0.5
            })

    def test_set_power_mode_fails_with_invalid_power_mode(self, power_meter):
        with pytest.raises(ValueError):
            power_meter.set_power_mode("invalid_mode")

    def test_measure(self, power_meter):
        assert power_meter.measure() == 20.0
        power_meter.set_power_mode("normal")
        assert power_meter.measure() == 16.0
        power_meter.set_power_mode("power-saving")
        assert power_meter.measure() == 8.0

class TestComputingSystem:

    @pytest.fixture
    def computing_system(self) -> ComputingSystem:
        return ComputingSystem(
            power_meters=[MockPowerMeter(p=5), MockPowerMeter(p=7)], pue=1.5
        )

    def test_consumption(self, computing_system):
        assert computing_system.consumption() == 18.0

    def test_finalize(self, computing_system):
        try:
            computing_system.finalize()
        except Exception as err:
            pytest.fail(f"Unexpected Error: {err}")
