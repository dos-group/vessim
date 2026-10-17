"""Grid constraints, priority dispatch, and explicit power balance."""

import json
import math

import pandas as pd
import pytest

import vessim as vs


def test_limits_and_unlimited_connection():
    assert vs.GridConnection().feasible_range(1) == (-math.inf, math.inf)
    grid = vs.GridConnection(max_import=5000, max_export=2000)
    assert grid.feasible_range(60) == (-5000, 2000)
    for power in (-5000, 0, 2000):
        grid.set_power(power, 60)
    for power in (-5001, 2001, math.inf, -math.inf, math.nan):
        with pytest.raises(ValueError):
            grid.set_power(power, 60)
    assert grid.current_power == 2000
    json.dumps(grid.config(), allow_nan=False)
    json.dumps(vs.GridConnection().config(), allow_nan=False)


@pytest.mark.parametrize("parameter", ["max_import", "max_export", "ramp_up", "ramp_down"])
@pytest.mark.parametrize("value", [-1, math.nan, math.inf, -math.inf])
def test_invalid_limits(parameter, value):
    with pytest.raises(ValueError):
        vs.GridConnection(**{parameter: value})


@pytest.mark.parametrize("power", [-101, 51, math.nan, math.inf])
def test_invalid_initial_power(power):
    with pytest.raises(ValueError):
        vs.GridConnection(max_import=100, max_export=50, initial_power=power)


def test_ramps_use_signed_power_and_previous_interval():
    grid = vs.GridConnection(initial_power=-5000, ramp_up=1000, ramp_down=2000)
    assert grid.feasible_range(60) == (-7000, -4000)
    grid.set_power(-4000, 60)
    # Setting a power twice must not allow multiple ramp increments in one tick.
    assert grid.feasible_range(60) == (-7000, -4000)
    with pytest.raises(ValueError, match="outside feasible range"):
        grid.set_power(-3000, 60)
    grid.step(60)
    assert grid.feasible_range(0.5) == (-6000, -3000)
    grid.set_power(-6000, 0.5)
    grid.step(0.5)
    assert grid.feasible_range(60) == (-8000, -5000)


def test_ramp_crosses_zero_and_respects_capacity():
    grid = vs.GridConnection(
        max_import=100, max_export=50, ramp_up=80, ramp_down=40, initial_power=-60
    )
    assert grid.feasible_range(1) == (-100, 20)
    grid.set_power(20, 1)
    grid.step(1)
    assert grid.feasible_range(1) == (-20, 50)


def test_disconnection_overrides_ramps_and_reconnects_from_zero():
    grid = vs.GridConnection(initial_power=-5000, ramp_up=1000, ramp_down=1000)
    grid.connected = False
    assert grid.feasible_range(60) == (0, 0)
    grid.set_power(0, 60)
    grid.step(60)
    grid.connected = True
    assert grid.feasible_range(60) == (-1000, 1000)


def test_changed_limits_must_not_silently_violate_ramps():
    grid = vs.GridConnection(initial_power=-5000, ramp_up=1000)
    grid.max_import = 1000
    with pytest.raises(ValueError, match="conflict"):
        grid.feasible_range(60)
    grid.max_import = -1
    with pytest.raises(ValueError, match="nonnegative"):
        grid.feasible_range(60)


class Generator(vs.Dispatchable):
    def feasible_range(self, duration):
        return (-1000, 0)

    def step(self, duration):
        pass

    def config(self):
        return {}

    def state(self):
        return {"current_power": self.current_power}


def test_grid_before_backup_generator():
    battery = vs.SimpleBattery("battery", 1000, initial_soc=0.5, c_rate=1)
    grid = vs.GridConnection(max_import=5000)
    backup = Generator("diesel")
    assert vs.DefaultDispatchPolicy().apply(-6500, 60, [battery, grid, backup]) is None
    assert [d.current_power for d in (battery, grid, backup)] == [-1000, -5000, -500]


@pytest.mark.parametrize("grid_first", [True, False])
@pytest.mark.parametrize(
    "initial,p_delta,battery_power", [(-5000, -3000, 1000), (5000, 3000, -1000)]
)
def test_mandatory_grid_power_is_reserved_before_flexible_dispatch(
    grid_first, initial, p_delta, battery_power
):
    battery = vs.SimpleBattery("battery", 10000, initial_soc=0.5)
    grid = vs.GridConnection(initial_power=initial, ramp_up=1000, ramp_down=1000)
    resources = [grid, battery] if grid_first else [battery, grid]
    assert vs.DefaultDispatchPolicy().apply(p_delta, 60, resources) is None
    assert battery.current_power == battery_power
    assert grid.current_power == p_delta - battery_power


def test_grid_priority_preserves_battery():
    battery = vs.SimpleBattery("battery", 1000, initial_soc=0.5)
    grid = vs.GridConnection()
    vs.DefaultDispatchPolicy().apply(-500, 60, [grid, battery])
    assert grid.current_power == -500
    assert battery.current_power == 0


def test_constraints_can_require_both_consumption_and_generation():
    importing = vs.GridConnection("import", initial_power=-5000, ramp_up=0, ramp_down=0)
    exporting = vs.GridConnection("export", initial_power=3000, ramp_up=0, ramp_down=0)
    battery = vs.SimpleBattery("battery", 10000, initial_soc=0.5)
    assert vs.DefaultDispatchPolicy().apply(-1000, 60, [battery, importing, exporting]) is None
    assert battery.current_power == 1000


def make_environment(power, resources, policy=None, backend="native", step_size=60):
    env = vs.Environment("2026-01-01", step_size=step_size, backend=backend)
    env.add_microgrid([vs.Actor("net", power=power)], resources, policy=policy, name="site")
    return env


@pytest.mark.parametrize("backend", ["native", "mosaik"])
def test_ramp_limited_trajectory_and_partial_final_interval(backend):
    if backend == "mosaik":
        pytest.importorskip("mosaik")
    grid = vs.GridConnection(max_import=5000, ramp_up=1000, ramp_down=1000)
    battery = vs.SimpleBattery("battery", 10000, initial_soc=0.5)
    trace = vs.Trace(pd.Series([-3000, -3000, 0], index=[0, 60, 120]))
    env = make_environment(trace, [grid, battery], backend=backend)
    rec = env.add_controller(vs.Recorder())
    env.run(120.5)
    rows = [states["site"] for states in rec.log.values()]
    assert [s["p_grid"] for s in rows] == [-1000, -2000, -1000]
    assert grid.current_power == -1000
    assert battery.charge_level == pytest.approx(5000 - 50 + 1000 * 0.5 / 3600)
    assert rec.metrics["microgrids"]["site"]["grid_import"] == pytest.approx(50 + 0.5 / 3.6)


@pytest.mark.parametrize("backend", ["native", "mosaik"])
def test_explicit_grid_export_recording(tmp_path, backend):
    if backend == "mosaik":
        pytest.importorskip("mosaik")
    grid = vs.GridConnection(max_export=100)
    env = make_environment(100, [grid], backend=backend)
    rec = env.add_controller(vs.Recorder(tmp_path))
    result = env.run(90)
    assert result.states["site"]["p_grid"] == 100
    assert rec.metrics["microgrids"]["site"]["grid_export"] == 2.5
    assert vs.ExperimentResult.load(tmp_path).metrics == rec.metrics
    assert rec.to_df()["p_grid"].tolist() == [100, 100]


@pytest.mark.parametrize("backend", ["native", "mosaik"])
@pytest.mark.parametrize("power", [-300, 300])
def test_unbalanced_dispatch_fails_without_recording_an_interval(tmp_path, backend, power):
    if backend == "mosaik":
        pytest.importorskip("mosaik")
    grid = vs.GridConnection(max_import=100, max_export=100)
    env = make_environment(power, [grid], backend=backend)
    rec = env.add_controller(vs.Recorder(tmp_path))
    with pytest.raises(RuntimeError, match="dispatch must balance exactly"):
        env.run(90)
    assert rec.steps == 0
    assert grid.current_power == 0  # Failed default allocation does not commit setpoints.
    assert vs.ExperimentResult.load(tmp_path).execution["status"] == "failed"


@pytest.mark.parametrize(
    "grid", [vs.GridConnection(max_import=10), vs.GridConnection(connected=False)]
)
def test_explicit_connection_never_gets_an_unlimited_fallback(grid):
    env = make_environment(-100, [grid])
    assert env.microgrids["site"].dispatchables == [grid]
    with pytest.raises(RuntimeError, match="Unmet demand"):
        env.run(60)
    assert env.status == "failed"


@pytest.mark.parametrize("resources", [None, [], [vs.GridConnection(connected=False)]])
@pytest.mark.parametrize("power", [-100, 100])
def test_no_connection_or_disconnected_connection_cannot_balance_power(resources, power):
    env = make_environment(power, resources)
    with pytest.raises(RuntimeError, match="dispatch must balance exactly"):
        env.run(60)


def test_no_implicit_grid_and_caller_list_is_preserved():
    resources = [vs.SimpleBattery("battery", 100, initial_soc=0.5)]
    env = make_environment(-10, resources)
    assert env.microgrids["site"].dispatchables == resources
    assert len(resources) == 1
    assert env.run(60).states["site"]["p_grid"] == 0


def test_empty_dispatchables_can_run_a_balanced_island():
    env = make_environment(0, [])
    state = env.run(60).states["site"]
    assert env.microgrids["site"].dispatchables == []
    assert state["dispatch_states"] == {}
    assert state["p_grid"] == 0


def test_fixed_charging_cannot_bypass_import_limit():
    env = make_environment(
        0,
        [vs.SimpleBattery("battery", 1000), vs.GridConnection(max_import=100)],
        policy=vs.DefaultDispatchPolicy(charge_power=200),
    )
    with pytest.raises(RuntimeError, match="Unmet demand of 100 W"):
        env.run(60)


def test_custom_policy_cannot_leave_unmet_demand():
    class BadPolicy(vs.DispatchPolicy):
        def apply(self, p_delta, duration, dispatchables, grid_signals=None):
            pass

    env = make_environment(-100, [vs.GridConnection(max_import=10)], policy=BadPolicy())
    with pytest.raises(RuntimeError, match="Unmet demand"):
        env.run(60)


def test_custom_policy_cannot_bypass_resource_limits():
    class BadPolicy(vs.DispatchPolicy):
        def apply(self, p_delta, duration, dispatchables, grid_signals=None):
            dispatchables[0].current_power = p_delta

    env = make_environment(-100, [vs.GridConnection(max_import=10)], policy=BadPolicy())
    with pytest.raises(ValueError, match="outside the feasible range"):
        env.run(60)


@pytest.mark.parametrize("backend", ["native", "mosaik"])
def test_controller_outage_and_reconnection(backend):
    if backend == "mosaik":
        pytest.importorskip("mosaik")
    grid = vs.GridConnection(ramp_up=50, ramp_down=50)
    battery = vs.SimpleBattery("battery", 1000, initial_soc=0.5)
    env = make_environment(-100, [grid, battery], backend=backend)

    class Outage(vs.Controller):
        def step(self, now, states):
            grid.connected = now.minute != 0

    env.add_controller(Outage())
    rec = env.add_controller(vs.Recorder())
    env.run(180)
    rows = [states["site"] for states in rec.log.values()]
    assert [s["p_grid"] for s in rows] == [-50, 0, -50]
    assert [s["dispatch_states"]["grid"]["connected"] for s in rows] == [True, False, True]
    assert battery.charge_level == pytest.approx(500 - 200 / 60)


def test_custom_policy_can_reorder_resources_without_changing_topology():
    class Reverse(vs.DefaultDispatchPolicy):
        def apply(self, p_delta, duration, dispatchables, grid_signals=None):
            dispatchables.reverse()
            super().apply(p_delta, duration, dispatchables, grid_signals)

    battery = vs.SimpleBattery("battery", 1000, initial_soc=0.5, c_rate=0.01)
    grid = vs.GridConnection(max_import=100)
    env = make_environment(-100, [battery, grid], policy=Reverse())
    state = env.run(60).states["site"]
    assert state["p_grid"] == -100
    assert battery.current_power == 0
    assert env.microgrids["site"].dispatchables == [battery, grid]


@pytest.mark.parametrize(
    "bounds", [(math.nan, 0), (0, math.nan), (1, -1), (math.inf, math.inf), (-math.inf, -math.inf)]
)
def test_invalid_custom_feasible_ranges_are_rejected(bounds):
    class Broken(Generator):
        def feasible_range(self, duration):
            return bounds

    with pytest.raises(ValueError, match="Invalid feasible range"):
        vs.DefaultDispatchPolicy().apply(0, 60, [Broken("broken")])


@pytest.mark.parametrize("power", [-1, 1])
def test_default_policy_rejects_even_a_tiny_nonzero_delta(power):
    grid = vs.GridConnection(max_import=1 - 1e-12, max_export=1 - 1e-12)
    with pytest.raises(RuntimeError, match="dispatch must balance exactly"):
        vs.DefaultDispatchPolicy().apply(power, 60, [grid])
    assert grid.current_power == 0


@pytest.mark.parametrize("error", [-1, 1, -1e-12, 1e-12])
def test_custom_policy_must_balance_without_tolerance(error):
    class Unbalanced(vs.DispatchPolicy):
        def apply(self, p_delta, duration, dispatchables, grid_signals=None):
            dispatchables[0].set_power(p_delta - error, duration)

    env = make_environment(10, [vs.GridConnection()], policy=Unbalanced())
    with pytest.raises(RuntimeError, match="dispatch must balance exactly"):
        env.run(60)


def test_default_policy_closes_fractional_delta_with_explicit_grid():
    battery = vs.SimpleBattery("battery", 10, initial_soc=0.5, c_rate=0.01)
    grid = vs.GridConnection()
    policy = vs.DefaultDispatchPolicy()
    assert policy.apply(0.3, 60, [battery, grid]) is None
    assert 0.3 - battery.current_power - grid.current_power == 0
