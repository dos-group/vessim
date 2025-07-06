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
        assert math.isclose(battery.soc(), exp_soc)

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
        assert math.isclose(battery_c.soc(), exp_soc)

    def test_update_fails_if_duration_not_positive(self, battery):
        with pytest.raises(ValueError):
            battery.update(10, -5)


class TestClcBattery:
    @pytest.fixture
    def battery(self) -> vs.ClcBattery:
        # Test battery for charging inefficiencies, current limits, number of cells and minimum SoC
        return vs.ClcBattery(
            number_of_cells=10,
            initial_soc=0.5,
            min_soc=0.1,
            u_1=0,
            v_1=0,
            u_2=0,
            v_2=10,
            alpha_d=-1,
            alpha_c=0.5,
            eta_c=0.5,
            eta_d=2,
        )

    @pytest.fixture
    def battery_u_energy(self) -> vs.ClcBattery:
        # Test battery for upper energy limits
        return vs.ClcBattery(
            initial_soc=0.75,
            nom_voltage=4,
            u_1=0,
            v_1=0,
            u_2=-1,
            v_2=10,
            alpha_c=1,
            eta_c=1,
        )

    @pytest.fixture
    def battery_l_energy(self) -> vs.ClcBattery:
        # Test battery for lower energy limits
        return vs.ClcBattery(
            initial_soc=0.25,
            nom_voltage=4,
            u_1=-1,
            v_1=0,
            u_2=0,
            v_2=10,
            alpha_d=-1,
            eta_d=1,
        )

    @pytest.mark.parametrize(
        "power, duration, exp_charge_energy, exp_charge_level, exp_soc",
        [
            # No charge
            (0, 1000, 0, 5, 0.5),
            # Charge
            (2.5, 60, 2.5, 6.25, 0.625),
            (5, 30, 2.5, 6.25, 0.625),
            (5, 60, 5, 7.5, 0.75),
            (5, 200, 10, 10, 1),  # try charging past capacity
            (10, 30, 2.5, 6.25, 0.625),  # exceeds charging limit of 5W per cell
            # Discharge
            (-2.5, 30, -1.25, 2.5, 0.25),
            (-5, 15, -1.25, 2.5, 0.25),
            (-10, 7.5, -1.25, 2.5, 0.25),
            (-20, 7.5, -1.25, 2.5, 0.25),  # exceeds discharging limit of -10W per cell
            (-10, 60, -2, 1.0, 0.1),  # Exceeds minimum SoC
        ],
    )
    def test_update(self, battery, power, duration, exp_charge_energy, exp_charge_level, exp_soc):
        # duration in minutes, energies in Wh, and power per cell
        charge_energy = battery.update(power=power * 10, duration=duration * 60)
        assert charge_energy == exp_charge_energy * 3600 * 10  # 10 cells
        assert battery.state()["charge_level"] == exp_charge_level * 10  # 10 cells
        assert math.isclose(battery.soc(), exp_soc)

    @pytest.mark.parametrize(
        "power, duration, exp_charge_energy, exp_charge_level",
        [
            (20, 5, 0.625, 8.125),  # limit for this step is 7.5W
            (20, 15, 1.25, 8.75),  # limit for this step is 5W
            (20, 45, 1.875, 9.375),  # limit for this step is 2.5W
        ],
    )
    def test_update_upper_energy_limits(
        self, battery_u_energy, power, duration, exp_charge_energy, exp_charge_level
    ):
        # duration in minutes, energies in Wh
        charge_energy = battery_u_energy.update(power=power, duration=duration * 60)
        assert charge_energy == exp_charge_energy * 3600
        assert battery_u_energy.state()["charge_level"] == exp_charge_level

    @pytest.mark.parametrize(
        "power, duration, exp_charge_energy, exp_charge_level",
        [
            (-20, 5, -0.625, 1.875),  # limit for this step is 7.5W
            (-20, 15, -1.25, 1.25),  # limit for this step is 5W
            (-20, 45, -1.875, 0.625),  # limit for this step is 2.5W
        ],
    )
    def test_update_lower_energy_limits(
        self, battery_l_energy, power, duration, exp_charge_energy, exp_charge_level
    ):
        # duration in minutes, energies in Wh
        charge_energy = battery_l_energy.update(power=power, duration=duration * 60)
        assert charge_energy == exp_charge_energy * 3600
        assert battery_l_energy.state()["charge_level"] == exp_charge_level


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
            (10, 4, 5, 1),
            # Discharge
            (-5, 2, 0, 0.7),
            (-10, 14, -5, 0.1),
        ],
    )
    def test_apply_no_charge_mode(self, battery, policy, power, duration, exp_delta, exp_soc):
        # duration in hours and power delta in W
        delta = policy.apply(power, duration * 3600, battery)
        assert delta == exp_delta
        assert math.isclose(battery.soc(), exp_soc)

    @pytest.mark.parametrize(
        "power, duration, exp_delta, exp_soc",
        [
            # Charge from grid without power-delta
            (0, 1, -10, 0.9),
            (0, 2, -10, 1),
            (0, 10, -2, 1),
            # Charge from grid with positive power-delta
            (5, 1, -5, 0.9),
            (5, 2, -5, 1),
            (5, 10, 3, 1),
            # Charge from grid with negative power-delta
            (-5, 1, -15, 0.9),
            (-5, 2, -15, 1),
            (-5, 10, -7, 1),
        ],
    )
    def test_apply_charge(self, battery, policy_charge, power, duration, exp_delta, exp_soc):
        # duration in hours and power delta in W
        delta = policy_charge.apply(power, duration * 3600, battery)
        assert delta == exp_delta
        assert math.isclose(battery.soc(), exp_soc)

    @pytest.mark.parametrize(
        "power, duration, exp_delta, exp_soc",
        [
            # Discharge to grid without power-delta
            (0, 1, 10, 0.7),
            (0, 7, 10, 0.1),
            (0, 10, 7, 0.1),
            # Discharge to grid with positive power-delta
            (5, 1, 15, 0.7),
            (5, 7, 15, 0.1),
            (5, 10, 12, 0.1),
            # Discharge to grid with negative power-delta
            (-5, 1, 5, 0.7),
            (-5, 7, 5, 0.1),
            (-5, 20, -1.5, 0.1),
        ],
    )
    def test_apply_discharge(self, battery, policy_discharge, power, duration, exp_delta, exp_soc):
        # duration in hours and power delta in W
        delta = policy_discharge.apply(power, duration * 3600, battery)
        assert delta == exp_delta
        assert math.isclose(battery.soc(), exp_soc)

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
        # duration in hours and power delta in W
        delta = policy_islanded.apply(power, duration * 3600, battery)
        assert delta == exp_delta
        assert math.isclose(battery.soc(), exp_soc)

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
        # duration in seconds and power delta in W
        delta = policy.apply(power, duration)
        assert delta == power

    def test_apply_fails_if_no_power_in_islanded_with_battery(self, battery, policy_islanded):
        with pytest.raises(RuntimeError):
            policy_islanded.apply(-1, 71 * 3600, battery)

    def test_apply_fails_if_no_power_in_islanded_without_battery(self, policy_islanded):
        with pytest.raises(RuntimeError):
            policy_islanded.apply(-1, 1)
