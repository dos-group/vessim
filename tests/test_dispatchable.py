import pytest
import math

import vessim as vs


class TestSimpleBattery:
    @pytest.fixture
    def battery(self) -> vs.SimpleBattery:
        return vs.SimpleBattery(name="bat", capacity=100, initial_soc=0.8, min_soc=0.1)

    @pytest.fixture
    def battery_c(self) -> vs.SimpleBattery:
        """This battery can only be (dis)charged at 10W max."""
        return vs.SimpleBattery(name="bat_c", capacity=10, initial_soc=0.5, c_rate=1)

    @pytest.mark.parametrize(
        "power, duration, exp_charge_level, exp_soc",
        [
            # No charge
            (0, 1000, 80, 0.8),
            # Charge
            (1, 1, 81, 0.81),
            (10, 2, 100, 1),
            # Discharge
            (-1, 1, 79, 0.79),
            (-10, 7, 10, 0.1),
        ],
    )
    def test_step(self, battery, power, duration, exp_charge_level, exp_soc):
        # duration in hours and charge_level in Wh
        battery.set_power(power, duration=duration * 3600)
        battery.step(duration=duration * 3600)
        assert battery.state()["charge_level"] == exp_charge_level
        assert math.isclose(battery.soc(), exp_soc)

    @pytest.mark.parametrize(
        "power, duration, exp_charge_level, exp_soc",
        [
            # No charge
            (0, 10, 5, 0.5),
            # Charge at c_rate limit
            (10, 6, 6, 0.6),
            # Discharge at c_rate limit
            (-10, 6, 4, 0.4),
            # Charge to full capacity
            (10, 30, 10, 1),
            # Discharge until empty
            (-10, 30, 0, 0),
        ],
    )
    def test_step_c_rate(
        self, battery_c, power, duration, exp_charge_level, exp_soc
    ):
        # duration in minutes and charge_level in Wh
        battery_c.set_power(power, duration=duration * 60)
        battery_c.step(duration=duration * 60)
        assert battery_c.state()["charge_level"] == exp_charge_level
        assert math.isclose(battery_c.soc(), exp_soc)

    def test_step_fails_if_duration_not_positive(self, battery):
        battery.set_power(10, duration=3600)
        with pytest.raises(ValueError):
            battery.step(-5)

    def test_feasible_range(self):
        battery = vs.SimpleBattery(name="bat", capacity=100, initial_soc=0.5, c_rate=2)
        # Over 1 hour, energy limit is 50Wh/1h = 50W, c_rate limit is 200W
        # Energy limit is binding
        lo, hi = battery.feasible_range(duration=3600)
        assert lo == -50.0
        assert hi == 50.0

    def test_feasible_range_c_rate_binding(self):
        # Short duration: c_rate should be binding, not energy
        battery = vs.SimpleBattery(name="bat", capacity=100, initial_soc=0.5, c_rate=2)
        lo, hi = battery.feasible_range(duration=1)
        assert lo == -200  # c_rate * capacity
        assert hi == 200

    def test_feasible_range_at_min_soc(self):
        battery = vs.SimpleBattery(name="bat", capacity=100, initial_soc=0.1, min_soc=0.1)
        lo, hi = battery.feasible_range(duration=3600)
        assert lo == 0.0  # Can't discharge further

    def test_feasible_range_at_full(self):
        battery = vs.SimpleBattery(name="bat", capacity=100, initial_soc=1.0)
        lo, hi = battery.feasible_range(duration=3600)
        assert hi == 0.0  # Can't charge further

    def test_feasible_range_energy_limited(self):
        # Battery at 80% SoC, 100Wh capacity, no c_rate.
        # Over 4 hours, can only charge 20Wh = 5W
        battery = vs.SimpleBattery(name="bat", capacity=100, initial_soc=0.8)
        lo, hi = battery.feasible_range(duration=4 * 3600)
        assert hi == 5.0  # 20Wh / 4h = 5W

    def test_set_power_raises_if_outside_range(self):
        # Short duration so c_rate is binding, not energy
        battery = vs.SimpleBattery(name="bat", capacity=100, initial_soc=0.5, c_rate=1)
        with pytest.raises(ValueError, match="outside feasible range"):
            battery.set_power(500, duration=1)


class TestClcBattery:
    @pytest.fixture
    def battery(self) -> vs.ClcBattery:
        return vs.ClcBattery(
            name="clc",
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
        return vs.ClcBattery(
            name="clc_u",
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
        return vs.ClcBattery(
            name="clc_l",
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
        "power, duration, exp_charge_level, exp_soc",
        [
            # No charge
            (0, 1000, 5, 0.5),
            # Charge
            (2.5, 60, 6.25, 0.625),
            (5, 30, 6.25, 0.625),
            (5, 60, 7.5, 0.75),
            # Discharge
            (-2.5, 30, 2.5, 0.25),
            (-5, 15, 2.5, 0.25),
            (-10, 7.5, 2.5, 0.25),
        ],
    )
    def test_step(self, battery, power, duration, exp_charge_level, exp_soc):
        # duration in minutes, power per cell
        battery.set_power(power * 10, duration=int(duration * 60))
        battery.step(duration=int(duration * 60))
        assert battery.state()["charge_level"] == exp_charge_level * 10  # 10 cells
        assert math.isclose(battery.soc(), exp_soc)

    def test_step_clipping(self, battery):
        # try charging past capacity
        # Max power for 200 min is (5 - 10) / (0 - 12000*0.5/3600) = -5 / -1.666 = 3W per cell
        # Total 30W.
        duration = 200 * 60
        max_p = battery.feasible_range(duration)[1]
        battery.set_power(max_p, duration=duration)
        battery.step(duration=duration)
        assert battery.soc() == 1.0

        # try discharging past min_soc
        # SoC 1.0 -> 0.1. Headroom 9Wh per cell. 90Wh total.
        # Max discharge for 60 min: (10 - 1) / (0 - 3600*2/3600) = 9 / -2 = -4.5W per cell
        # Total -45W.
        duration = 60 * 60
        min_p = battery.feasible_range(duration)[0]
        battery.set_power(min_p, duration=duration)
        battery.step(duration=duration)
        assert battery.soc() == 0.1

    def test_feasible_range(self, battery):
        # 10 cells, 0.5 SoC, alpha_d=-1, alpha_c=0.5
        # v_2=10, initial charge level = 5
        # u_1=0, v_1=0, u_2=0, v_2=10, eta_c=0.5, eta_d=2, nom_voltage=3.63
        # Small duration: limited by alpha
        assert battery.feasible_range(60) == (-100, 50)

        # Large duration: limited by energy
        # For charging: (5 - 10) / (0/3.63 - 3600*0.5/3600) = -5 / -0.5 = 10W per cell
        # 10W > alpha_c=0.5, so still limited by alpha (5W per cell * 10 cells = 50W)
        # For discharging: (5 - 0) / (0/3.63 - 3600*2/3600) = 5 / -2 = -2.5W per cell
        # -2.5W > alpha_d=-10, so limited by energy (-25W total)
        assert battery.feasible_range(3600) == (-25, 50)

    @pytest.mark.parametrize(
        "power, duration, exp_charge_level",
        [
            (1, 5, 7.583333333333333),
            (1, 15, 7.75),
            (0.5, 45, 7.875), # energy limit for 45 min is 1.666W. 0.5W is safe.
        ],
    )
    def test_step_upper_energy_limits(
        self, battery_u_energy, power, duration, exp_charge_level
    ):
        # duration in minutes
        battery_u_energy.set_power(power, duration=duration * 60)
        battery_u_energy.step(duration=duration * 60)
        assert math.isclose(battery_u_energy.state()["charge_level"], exp_charge_level)

    def test_feasible_range_u_energy(self, battery_u_energy):
        # initial_soc=0.75, v_2=10, charge_level=7.5, u_2=-1, alpha_c=1, eta_c=1, nom_voltage=4
        # alpha_c constructor param is C-rate. alpha_c_watt = 1 * 10 = 10W.
        # duration 3600s:
        # max_power = (7.5 - 10) / (-1/4 - 3600*1/3600) = -2.5 / -1.25 = 2W
        # 2W < 10W. So limited by energy (2W).
        assert battery_u_energy.feasible_range(3600)[1] == 2

    @pytest.mark.parametrize(
        "power, duration, exp_charge_level",
        [
            (-1, 5, 2.4166666666666665),
            (-1, 15, 2.25),
            (-0.5, 45, 2.125),
        ],
    )
    def test_step_lower_energy_limits(
        self, battery_l_energy, power, duration, exp_charge_level
    ):
        # duration in minutes
        battery_l_energy.set_power(power, duration=duration * 60)
        battery_l_energy.step(duration=duration * 60)
        assert math.isclose(battery_l_energy.state()["charge_level"], exp_charge_level)


class TestDefaultDispatchPolicy:
    @pytest.fixture
    def battery(self) -> vs.SimpleBattery:
        return vs.SimpleBattery(name="bat", capacity=100, initial_soc=0.8, min_soc=0.1)

    @pytest.fixture
    def policy(self) -> vs.DefaultDispatchPolicy:
        return vs.DefaultDispatchPolicy()

    @pytest.fixture
    def policy_charge(self) -> vs.DefaultDispatchPolicy:
        return vs.DefaultDispatchPolicy(charge_power=10)

    @pytest.fixture
    def policy_islanded(self) -> vs.DefaultDispatchPolicy:
        return vs.DefaultDispatchPolicy(mode="islanded")

    @pytest.mark.parametrize(
        "power, duration, exp_delta, exp_soc",
        [
            # No charge
            (0, 1000, 0, 0.8),
            # Charge (positive p_delta = excess power)
            (5, 2, 0, 0.9),
            (10, 4, 5, 1),
            # Discharge (negative p_delta = power deficit)
            (-5, 2, 0, 0.7),
            (-10, 14, -5, 0.1),
        ],
    )
    def test_apply_merit_order(self, battery, policy, power, duration, exp_delta, exp_soc):
        # duration in hours
        p_grid = policy.apply(power, duration * 3600, [battery])
        battery.step(duration * 3600)
        assert p_grid == exp_delta
        assert math.isclose(battery.soc(), exp_soc)

    @pytest.mark.parametrize(
        "power, duration, exp_delta, exp_soc",
        [
            # Charge from grid without power-delta
            (0, 1, -10, 0.9),
            (0, 2, -10, 1),
            # Charge from grid with positive power-delta
            (5, 1, -5, 0.9),
            # Charge from grid with negative power-delta
            (-5, 1, -15, 0.9),
        ],
    )
    def test_apply_charge_power(self, battery, policy_charge, power, duration, exp_delta, exp_soc):
        # duration in hours
        p_grid = policy_charge.apply(power, duration * 3600, [battery])
        battery.step(duration * 3600)
        assert p_grid == exp_delta
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
        # duration in hours
        p_grid = policy_islanded.apply(power, duration * 3600, [battery])
        battery.step(duration * 3600)
        assert p_grid == exp_delta
        assert math.isclose(battery.soc(), exp_soc)

    @pytest.mark.parametrize(
        "power, duration",
        [
            (0, 1000),
            (5, 2),
            (-5, 2),
        ],
    )
    def test_apply_no_dispatchables(self, policy, power, duration):
        # With no dispatchables, all power goes to grid
        p_grid = policy.apply(power, duration, [])
        assert p_grid == power

    def test_apply_fails_if_no_power_in_islanded(self, battery, policy_islanded):
        with pytest.raises(RuntimeError):
            policy_islanded.apply(-1, 71 * 3600, [battery])

    def test_apply_fails_if_no_power_in_islanded_without_dispatchables(self, policy_islanded):
        with pytest.raises(RuntimeError):
            policy_islanded.apply(-1, 1, [])
