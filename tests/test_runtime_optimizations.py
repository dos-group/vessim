"""Guard numerical and extension behavior of the optimized native tick."""

from datetime import timedelta
from decimal import Decimal
from fractions import Fraction

import numpy as np
import pandas as pd
import pytest

import vessim as vs
from vessim._util import require_finite


@pytest.mark.parametrize(
    "value", [0, -2, 0.5, np.float64(0.5), np.float32(0.5), np.int64(2), Fraction(1, 3)]
)
def test_numeric_validation_accepts_real_scalar_types(value):
    require_finite(value, "test")


@pytest.mark.parametrize(
    "value",
    [
        True,
        np.bool_(False),
        "1",
        None,
        complex(1),
        Decimal("1"),
        np.array([1]),
        float("nan"),
        float("inf"),
        np.float64("nan"),
        np.float32("inf"),
    ],
)
def test_numeric_validation_rejects_nonreal_and_nonfinite_values(value):
    with pytest.raises(ValueError, match="finite number"):
        require_finite(value, "test")


@pytest.mark.parametrize("fill", ["ffill", "bfill"])
@pytest.mark.parametrize("spacing", [0.000002, 0.25, 300, 3600])
def test_regular_trace_matches_search_for_arbitrary_query_order(fill, spacing):
    offsets = np.arange(20) * spacing
    values = np.arange(20, dtype=float) ** 2
    frame = pd.DataFrame({"first": values, "second": -values}, index=offsets)
    trace = vs.Trace(frame, fill_method=fill)
    selected = trace.select("second")
    rng = np.random.default_rng(42)
    queries = np.concatenate([offsets, rng.uniform(0, offsets[-1], 100)])
    rng.shuffle(queries)
    ns = pd.to_timedelta(offsets, unit="s").to_numpy().astype("timedelta64[ns]").view("i8")
    for elapsed in queries:
        at = round(elapsed * 1_000_000) * 1000
        index = np.searchsorted(ns, at, side="right" if fill == "ffill" else "left")
        if fill == "ffill":
            index -= 1
        assert trace.at(float(elapsed), "first") == values[index]
        assert selected.at(timedelta(seconds=float(elapsed))) == -values[index]


@pytest.mark.parametrize("fill", ["ffill", "bfill"])
def test_irregular_and_single_sample_traces_retain_lookup_behavior(fill):
    trace = vs.Trace(pd.Series([1, 2, 3], index=[0, 1, 3]), fill_method=fill)
    assert trace.at(2) == (2 if fill == "ffill" else 3)
    assert trace.at(1) == 2
    single = vs.Trace(pd.Series([7], index=[0]), fill_method=fill)
    assert single.at(0) == 7
    with pytest.raises(ValueError, match="after the end"):
        single.at(0.1)


def test_builtin_ranges_are_reused_only_within_one_dispatch(monkeypatch):
    calls = []
    original = vs.GridConnection.feasible_range

    def observed(self, duration):
        calls.append((duration, self.max_import))
        return original(self, duration)

    monkeypatch.setattr(vs.GridConnection, "feasible_range", observed)
    connection = vs.GridConnection(max_import=100)
    battery = vs.SimpleBattery("battery", 1000, initial_soc=0.5)
    env = vs.Environment("2026-01-01", step_size=60)
    env.add_microgrid([vs.Consumer("load", 100)], [connection, battery], name="site")

    class Limit(vs.Controller):
        def step(self, now, states):
            connection.max_import = 25

    env.add_controller(Limit())
    rec = env.add_controller(vs.Recorder())
    env.run(90)
    assert calls == [(60, 100), (30, 25)]
    assert [states["site"]["p_grid"] for states in rec.log.values()] == [-100, -25]
    assert battery.charge_level == pytest.approx(500 - 75 * 30 / 3600)


def test_custom_setpoint_hook_runs_and_uses_updated_limits():
    class Limited(vs.GridConnection):
        def set_power(self, power, duration):
            self.max_import = 10
            super().set_power(power, duration)

    connection = Limited()
    env = vs.Environment("2026-01-01")
    env.add_microgrid([vs.Consumer("load", 100)], [connection])
    with pytest.raises(ValueError, match="outside feasible range"):
        env.run(1)
    assert connection.current_power == 0


def test_valid_battery_limit_does_not_log(monkeypatch):
    from vessim.dispatchable import logger

    messages = []
    monkeypatch.setattr(logger, "info", lambda *args, **kwargs: messages.append(args))
    battery = vs.SimpleBattery("battery", 1000, initial_soc=0.5, c_rate=0.1)
    for power in (100, -100):
        battery.set_power(power, 60)
        battery.step(60)
    assert messages == []
    assert battery.charge_level == pytest.approx(500)
