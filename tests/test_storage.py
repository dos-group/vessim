import pytest
import math

import vessim as vs


class TestSimpleBattery:
    @pytest.fixture
    def battery(self) -> vs.SimpleBattery:
        return vs.SimpleBattery(capacity=100, initial_soc=0.8, min_soc=0.1)

    @pytest.fixture
    def battery_c(self) -> vs.SimpleBattery:
        """This battery can only be (dis)charged at 10W max."""
        return vs.SimpleBattery(capacity=10, initial_soc=0.5, c_rate=1)

    @pytest.mark.parametrize(
        "power, duration, exp_charge_energy, exp_charge_level, exp_soc",
        [
            # No charge
            (0, 1000, 0, 80, 0.8),
            # Charge
            (1, 1, 1, 81, 0.81),
            (10, 2, 20, 100, 1),
            (10, 4, 20, 100, 1),
            (100, 4, 20, 100, 1),
            # Discharge
            (-1, 1, -1, 79, 0.79),
            (-10, 7, -70, 10, 0.1),
            (-15, 7, -70, 10, 0.1),
            (-10, 14, -70, 10, 0.1),
        ],
    )
    def test_update(self, battery, power, duration, exp_charge_energy, exp_charge_level, exp_soc):
        # duration in hours and charge_level in Wh
        charge_energy = battery.update(power=power, duration=duration * 3600)
        assert charge_energy == exp_charge_energy * 3600
        assert battery.state()["charge_level"] == exp_charge_level
        assert math.isclose(battery.state()["soc"], exp_soc)

    @pytest.mark.parametrize(
        "power, duration, exp_charge_energy, exp_charge_level, exp_soc",
        [
            # No charge
            (0, 10, 0, 5, 0.5),
            # Charge
            (10, 6, 1, 6, 0.6),
            (20, 6, 1, 6, 0.6),
            (50, 6, 1, 6, 0.6),
            # Discharge
            (-10, 6, -1, 4, 0.4),
            (-20, 6, -1, 4, 0.4),
            (-50, 6, -1, 4, 0.4),
            # Charge over capacity
            (10, 30, 5, 10, 1),
            (10, 40, 5, 10, 1),
            (15, 40, 5, 10, 1),
            # Discharge until empty
            (-10, 30, -5, 0, 0),
            (-10, 40, -5, 0, 0),
            (-15, 40, -5, 0, 0),
        ],
    )
    def test_update_c_rate(
        self, battery_c, power, duration, exp_charge_energy, exp_charge_level, exp_soc
    ):
        # duration in minutes and charge_level in Wh
        charge_energy = battery_c.update(power=power, duration=duration * 60)
        assert charge_energy == exp_charge_energy * 3600
        assert battery_c.state()["charge_level"] == exp_charge_level
        assert math.isclose(battery_c.state()["soc"], exp_soc)

    def test_update_fails_if_duration_not_positive(self, battery):
        with pytest.raises(ValueError):
            battery.update(10, -5)


class TestDefaultMicrogridPolicy:
    @pytest.fixture
    def battery(self) -> vs.SimpleBattery:
        return vs.SimpleBattery(capacity=100, initial_soc=0.8, min_soc=0.1)

    @pytest.fixture
    def policy(self) -> vs.DefaultMicrogridPolicy:
        return vs.DefaultMicrogridPolicy()

    @pytest.fixture
    def policy_charge(self) -> vs.DefaultMicrogridPolicy:
        return vs.DefaultMicrogridPolicy(charge_power=10)

    @pytest.fixture
    def policy_discharge(self) -> vs.DefaultMicrogridPolicy:
        return vs.DefaultMicrogridPolicy(charge_power=-10)

    @pytest.fixture
    def policy_islanded(self) -> vs.DefaultMicrogridPolicy:
        return vs.DefaultMicrogridPolicy(mode="islanded")

    @pytest.mark.parametrize(
        "power, duration, exp_delta, exp_soc",
        [
            # No charge
            (0, 1000, 0, 0.8),
            # Charge
            (5, 2, 0, 0.9),
            (10, 4, 20, 1),
            # Discharge
            (-5, 2, 0, 0.7),
            (-10, 14, -70, 0.1),
        ],
    )
    def test_apply_no_charge_mode(self, battery, policy, power, duration, exp_delta, exp_soc):
        # duration in hours and energy delta in Wh
        delta = policy.apply(power, duration * 3600, battery)
        assert delta == exp_delta * 3600
        assert math.isclose(battery.state()["soc"], exp_soc)

    @pytest.mark.parametrize(
        "power, duration, exp_delta, exp_soc",
        [
            # Charge from grid without power-delta
            (0, 1, -10, 0.9),
            (0, 2, -20, 1),
            (0, 10, -20, 1),
            # Charge from grid with positive power-delta
            (5, 1, -5, 0.9),
            (5, 2, -10, 1),
            (5, 10, 30, 1),
            # Charge from grid with negative power-delta
            (-5, 1, -15, 0.9),
            (-5, 2, -30, 1),
            (-5, 10, -70, 1),
        ],
    )
    def test_apply_charge(self, battery, policy_charge, power, duration, exp_delta, exp_soc):
        # duration in hours and energy delta in Wh
        delta = policy_charge.apply(power, duration * 3600, battery)
        assert delta == exp_delta * 3600
        assert math.isclose(battery.state()["soc"], exp_soc)

    @pytest.mark.parametrize(
        "power, duration, exp_delta, exp_soc",
        [
            # Discharge to grid without power-delta
            (0, 1, 10, 0.7),
            (0, 7, 70, 0.1),
            (0, 10, 70, 0.1),
            # Discharge to grid with positive power-delta
            (5, 1, 15, 0.7),
            (5, 7, 105, 0.1),
            (5, 10, 120, 0.1),
            # Discharge to grid with negative power-delta
            (-5, 1, 5, 0.7),
            (-5, 7, 35, 0.1),
            (-5, 20, -30, 0.1),
        ],
    )
    def test_apply_discharge(self, battery, policy_discharge, power, duration, exp_delta, exp_soc):
        # duration in hours and energy delta in Wh
        delta = policy_discharge.apply(power, duration * 3600, battery)
        assert delta == exp_delta * 3600
        assert math.isclose(battery.state()["soc"], exp_soc)

    @pytest.mark.parametrize(
        "power, duration, exp_delta, exp_soc",
        [
            # No charge
            (0, 1000, 0, 0.8),
            # Charge
            (5, 2, 0, 0.9),
            (100, 4, 0, 1),
            # Discharge
            (-5, 2, 0, 0.7),
            (-10, 7, 0, 0.1),
        ],
    )
    def test_apply_islanded(self, battery, policy_islanded, power, duration, exp_delta, exp_soc):
        # duration in hours and energy delta in Wh
        delta = policy_islanded.apply(power, duration * 3600, battery)
        assert delta == exp_delta * 3600
        assert math.isclose(battery.state()["soc"], exp_soc)

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
        # duration in seconds and energy delta in Ws
        delta = policy.apply(power, duration)
        assert delta == exp_delta

    def test_apply_fails_if_no_power_in_islanded_with_battery(self, battery, policy_islanded):
        with pytest.raises(RuntimeError):
            policy_islanded.apply(-1, 71 * 3600, battery)

    def test_apply_fails_if_no_power_in_islanded_without_battery(self, policy_islanded):
        with pytest.raises(RuntimeError):
            policy_islanded.apply(-1, 1)
