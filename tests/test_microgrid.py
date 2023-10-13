import pytest
from typing import Dict

from vessim.core.microgrid import SimpleMicrogrid
from vessim.core.storage import SimpleBattery


class TestSimpleMicrogrid:
    @pytest.fixture
    def microgrid(self) -> SimpleMicrogrid:
        return SimpleMicrogrid()

    @pytest.fixture
    def microgrid_battery(self) -> SimpleMicrogrid:
        return SimpleMicrogrid(
            storage=SimpleBattery(capacity=100, charge_level=80, min_soc=0.1)
        )

    @pytest.fixture
    def power_values(self) -> Dict:
        return {
            "Consumer_0": -15,
            "Consumer_1": -10,
            "Generator_0": 20,
            "Generator_1": 0,
        }

    def test_power_flow(self, microgrid, power_values):
        assert microgrid.power_flow(power_values, 10) == -5

    def test_power_flow_with_storage(self, microgrid_battery, power_values):
        p_delta = microgrid_battery.power_flow(power_values, 10)
        assert p_delta == 0
        assert microgrid_battery.storage.charge_level == 30
