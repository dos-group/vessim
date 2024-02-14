import pytest

from vessim.storage import SimpleBattery, DefaultStoragePolicy


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
        "power, duration, exp_delta, exp_charge_level",
        [
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
        ],
    )
    def test_update(self, battery, power, duration, exp_delta, exp_charge_level):
        delta = battery.update(power=power, duration=duration)
        assert delta == exp_delta
        assert battery.charge_level == exp_charge_level

    @pytest.mark.parametrize(
        "power, duration, exp_delta, exp_charge_level",
        [
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
        ],
    )
    def test_update_c_rate(self, battery_c, power, duration, exp_delta, exp_charge_level):
        delta = battery_c.update(power=power, duration=duration)
        assert delta == exp_delta
        assert battery_c.charge_level == exp_charge_level

    def test_update_fails_if_duration_not_positive(self, battery):
        with pytest.raises(ValueError):
            battery.update(10, -5)


class TestDefaultStoragePolicy:
    @pytest.fixture
    def battery(self) -> SimpleBattery:
        return SimpleBattery(capacity=100, charge_level=80, min_soc=0.1)

    @pytest.fixture
    def policy(self) -> DefaultStoragePolicy:
        return DefaultStoragePolicy()

    @pytest.fixture
    def policy_charge(self) -> DefaultStoragePolicy:
        return DefaultStoragePolicy(grid_power=10)

    @pytest.fixture
    def policy_discharge(self) -> DefaultStoragePolicy:
        return DefaultStoragePolicy(grid_power=-10)

    @pytest.mark.parametrize(
        "power, duration, exp_delta, exp_charge_level",
        [
            # No charge
            (0, 1000, 0, 80),
            # Charge
            (100, 4, 95, 100),
            # Discharge
            (-10, 14, -5, 10),
        ],
    )
    def test_apply_no_charge_mode(
        self, battery, policy, power, duration, exp_delta, exp_charge_level
    ):
        delta = policy.apply(
            storage=battery, p_delta=power, time_since_last_step=duration
        )
        assert delta == exp_delta
        assert battery.charge_level == exp_charge_level

    @pytest.mark.parametrize(
        "power, duration, exp_delta, exp_charge_level",
        [
            # Charge from grid without power-delta
            (0, 1, -10, 90),
            (0, 2, -10, 100),
            (0, 10, -2, 100),
            (0, 20, -1, 100),
            # Charge from grid with positive power-delta
            (5, 1, -5, 90),
            (5, 2, -5, 100),
            (5, 10, 3, 100),
            (5, 20, 4, 100),
            # Charge from grid with negative power-delta
            (-5, 1, -15, 90),
            (-5, 2, -15, 100),
            (-5, 10, -7, 100),
            (-5, 20, -6, 100),
        ],
    )
    def test_apply_charge(
        self, battery, policy_charge, power, duration, exp_delta, exp_charge_level
    ):
        delta = policy_charge.apply(
            storage=battery, p_delta=power, time_since_last_step=duration
        )
        assert delta == exp_delta
        assert battery.charge_level == exp_charge_level

    @pytest.mark.parametrize(
        "power, duration, exp_delta, exp_charge_level",
        [
            # Discharge to grid without power-delta
            (0, 1, 10, 70),
            (0, 7, 10, 10),
            (0, 10, 7, 10),
            (0, 70, 1, 10),
            # Discharge to grid with positive power-delta
            (5, 1, 15, 70),
            (5, 7, 15, 10),
            (5, 10, 12, 10),
            (5, 70, 6, 10),
            # Discharge to grid with negative power-delta
            (-5, 1, 5, 70),
            (-5, 7, 5, 10),
            (-5, 10, 2, 10),
            (-5, 70, -4, 10),
        ],
    )
    def test_apply_discharge(
        self, battery, policy_discharge, power, duration, exp_delta, exp_charge_level
    ):
        delta = policy_discharge.apply(
            storage=battery, p_delta=power, time_since_last_step=duration
        )
        assert delta == exp_delta
        assert battery.charge_level == exp_charge_level
