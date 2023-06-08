import pytest

from vessim.storage import SimpleBattery


class TestSimpleBattery:

    @pytest.fixture
    def battery(self) -> SimpleBattery:
        return SimpleBattery(capacity=100, charge_level=80, min_soc=0.1)

    @pytest.fixture
    def battery_c(self) -> SimpleBattery:
        """This battery can only be (dis)charged at 10W max."""
        return SimpleBattery(capacity=3600, charge_level=1800, c_rate=10)

    def test_soc(self, battery):
        assert battery.soc() == 0.8

    @pytest.mark.parametrize("power, duration, exp_delta, exp_charge_level", [
        # No charge
        (0, 1000, 0, 80),
        # Charge
        (1, 1, 0, 81),
        (10, 2, 0, 100),
        (10, 4, 5, 100),
        (100, 4, 95, 100),
        # Discharge
        (-1, 1, 0, 79),
        (-10, 7, 0, 10),
        (-15, 7, -5, 10),
        (-10, 14, -5, 10),
    ])
    def test_update(self, battery, power, duration, exp_delta, exp_charge_level):
        delta = battery.update(power=power, duration=duration)
        assert delta == exp_delta
        assert battery.charge_level == exp_charge_level

    @pytest.mark.parametrize("power, duration, exp_delta, exp_charge_level", [
        # No charge
        (0, 10, 0, 1800),
        # Charge
        (10, 10, 0, 1900),
        (20, 10, 10, 1900),
        (50, 10, 40, 1900),
        # Discharge
        (-10, 10, 0, 1700),
        (-20, 10, -10, 1700),
        (-50, 10, -40, 1700),
        # Charge over capacity
        (10, 180, 0, 3600),
        (10, 200, 1, 3600),
        (15, 200, 6, 3600),
        # Discharge untl empty
        (-10, 180, 0, 0),
        (-10, 200, -1, 0),
        (-15, 200, -6, 0),
    ])
    def test_update_c_rate(self, battery_c, power, duration, exp_delta, exp_charge_level):
        delta = battery_c.update(power=power, duration=duration)
        assert delta == exp_delta
        assert battery_c.charge_level == exp_charge_level
