import pytest

from vessim.storage import SimpleBattery
from vessim.cosim import DefaultMicrogridPolicy


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

    @pytest.mark.parametrize(
        "power, duration, exp_charge_energy, exp_charge_level",
        [
            # No charge
            (0, 1000, 0, 80),
            # Charge
            (1, 1, 1, 81),
            (10, 2, 20, 100),
            (10, 4, 20, 100),
            (100, 4, 20, 100),
            # Discharge
            (-1, 1, -1, 79),
            (-10, 7, -70, 10),
            (-15, 7, -70, 10),
            (-10, 14, -70, 10),
        ],
    )
    def test_update(self, battery, power, duration, exp_charge_energy, exp_charge_level):
        charge_energy = battery.update(power=power, duration=duration)
        assert charge_energy == exp_charge_energy
        assert battery.charge_level == exp_charge_level

    @pytest.mark.parametrize(
        "power, duration, exp_delta, exp_charge_level",
        [
            # No charge
            (0, 10, 0, 1800),
            # Charge
            (10, 10, 100, 1900),
            (20, 10, 100, 1900),
            (50, 10, 100, 1900),
            # Discharge
            (-10, 10, -100, 1700),
            (-20, 10, -100, 1700),
            (-50, 10, -100, 1700),
            # Charge over capacity
            (10, 180, 1800, 3600),
            (10, 200, 1800, 3600),
            (15, 200, 1800, 3600),
            # Discharge until empty
            (-10, 180, -1800, 0),
            (-10, 200, -1800, 0),
            (-15, 200, -1800, 0),
        ],
    )
    def test_update_c_rate(self, battery_c, power, duration, exp_delta, exp_charge_level):
        delta = battery_c.update(power=power, duration=duration)
        assert delta == exp_delta
        assert battery_c.charge_level == exp_charge_level

    def test_update_fails_if_duration_not_positive(self, battery):
        with pytest.raises(ValueError):
            battery.update(10, -5)


class TestDefaultMicrogridPolicy:
    @pytest.fixture
    def battery(self) -> SimpleBattery:
        return SimpleBattery(capacity=100, charge_level=80, min_soc=0.1)

    @pytest.fixture
    def policy(self) -> DefaultMicrogridPolicy:
        return DefaultMicrogridPolicy()

    @pytest.fixture
    def policy_charge(self) -> DefaultMicrogridPolicy:
        return DefaultMicrogridPolicy(charge_power=10)

    @pytest.fixture
    def policy_discharge(self) -> DefaultMicrogridPolicy:
        return DefaultMicrogridPolicy(charge_power=-10)

    @pytest.fixture
    def policy_islanded(self) -> DefaultMicrogridPolicy:
        return DefaultMicrogridPolicy(mode="islanded")

    @pytest.mark.parametrize(
        "power, duration, exp_delta, exp_charge_level",
        [
            # No charge
            (0, 1000, 0, 80),
            # Charge
            (5, 2, 0, 90),
            (100, 4, 380, 100),
            # Discharge
            (-5, 2, 0, 70),
            (-10, 14, -70, 10),
        ],
    )
    def test_apply_no_charge_mode(
        self, battery, policy, power, duration, exp_delta, exp_charge_level
    ):
        delta = policy.apply(power, duration, battery)
        assert delta == exp_delta
        assert battery.charge_level == exp_charge_level

    @pytest.mark.parametrize(
        "power, duration, exp_delta, exp_charge_level",
        [
            # Charge from grid without power-delta
            (0, 1, -10, 90),
            (0, 2, -20, 100),
            (0, 10, -20, 100),
            # Charge from grid with positive power-delta
            (5, 1, -5, 90),
            (5, 2, -10, 100),
            (5, 10, 30, 100),
            # Charge from grid with negative power-delta
            (-5, 1, -15, 90),
            (-5, 2, -30, 100),
            (-5, 10, -70, 100),
        ],
    )
    def test_apply_charge(
        self, battery, policy_charge, power, duration, exp_delta, exp_charge_level
    ):
        delta = policy_charge.apply(power, duration, battery)
        assert delta == exp_delta
        assert battery.charge_level == exp_charge_level

    @pytest.mark.parametrize(
        "power, duration, exp_delta, exp_charge_level",
        [
            # Discharge to grid without power-delta
            (0, 1, 10, 70),
            (0, 7, 70, 10),
            (0, 10, 70, 10),
            # Discharge to grid with positive power-delta
            (5, 1, 15, 70),
            (5, 7, 105, 10),
            (5, 10, 120, 10),
            # Discharge to grid with negative power-delta
            (-5, 1, 5, 70),
            (-5, 7, 35, 10),
            (-5, 20, -30, 10),
        ],
    )
    def test_apply_discharge(
        self, battery, policy_discharge, power, duration, exp_delta, exp_charge_level
    ):
        delta = policy_discharge.apply(power, duration, battery)
        assert delta == exp_delta
        assert battery.charge_level == exp_charge_level

    @pytest.mark.parametrize(
        "power, duration, exp_delta, exp_charge_level",
        [
            # No charge
            (0, 1000, 0, 80),
            # Charge
            (5, 2, 0, 90),
            (100, 4, 0, 100),
            # Discharge
            (-5, 2, 0, 70),
            (-10, 7, 0, 10),
        ],
    )
    def test_apply_islanded(
        self, battery, policy_islanded, power, duration, exp_delta, exp_charge_level
    ):
        delta = policy_islanded.apply(power, duration, battery)
        assert delta == exp_delta
        assert battery.charge_level == exp_charge_level

    @pytest.mark.parametrize(
        "power, duration, exp_delta",
        [
            # Zero delta
            (0, 1000, 0),
            # Positive delta
            (5, 2, 10),
            (100, 4, 400),
            # Negative delta
            (-5, 2, -10),
            (-100, 4, -400),
        ],
    )
    def test_apply_no_storage(self, policy, power, duration, exp_delta):
        delta = policy.apply(power, duration)
        assert delta == exp_delta

    def test_apply_fails_if_no_power_in_islanded_with_battery(self, battery, policy_islanded):
        with pytest.raises(RuntimeError):
            policy_islanded.apply(-1, 71, battery)

    def test_apply_fails_if_no_power_in_islanded_without_battery(self, policy_islanded):
        with pytest.raises(RuntimeError):
            policy_islanded.apply(-1, 1)
