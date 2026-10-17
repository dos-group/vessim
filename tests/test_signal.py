from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

import vessim as vs


class TestTrace:
    @pytest.fixture
    def hist_signal(self) -> vs.Trace:
        index = pd.to_datetime(
            [
                "2023-01-01T00:00:00",
                "2023-01-01T00:30:00",
                "2023-01-01T01:00:00",
            ]
        )
        actual = pd.DataFrame(
            {"a": [1, 2, 3], "b": [0, 3, 0], "c": [0, 4, 0]}, index=index - index[0]
        )
        return vs.Trace(actual)

    @pytest.fixture
    def hist_signal_single(self) -> vs.Trace:
        index = pd.to_datetime(
            ["2023-01-01T01:00:00", "2023-01-01T00:30:00", "2023-01-01T00:00:00"]
        )
        actual = pd.Series([3, 2, 1], index=index - index.min())
        return vs.Trace(actual, fill_method="bfill")

    def test_columns(self, hist_signal):
        assert hist_signal.columns() == ["a", "b", "c"]

    def test_actual_single_column(self, hist_signal_single):
        assert hist_signal_single.at(timedelta(minutes=45)) == 3

    @pytest.mark.parametrize(
        "elapsed, column, expected",
        [
            (timedelta(0), "a", 1),
            (timedelta(seconds=10), "a", 1),
            (timedelta(hours=1), "a", 3),
            (timedelta(minutes=29, seconds=59), "b", 0),
            (timedelta(minutes=30), "b", 3),
        ],
    )
    def test_actual(self, hist_signal, elapsed, column, expected):
        assert hist_signal.at(elapsed, column) == expected

    def test_accepts_int_seconds(self, hist_signal_single):
        # int/float should be coerced to timedelta(seconds=...)
        assert hist_signal_single.at(2700) == hist_signal_single.at(timedelta(seconds=2700))

    def test_accepts_float_seconds(self, hist_signal_single):
        assert hist_signal_single.at(1800.0) == hist_signal_single.at(timedelta(minutes=30))

    def test_actual_fails_if_invalid_kwargs(self, hist_signal_single):
        with pytest.raises(TypeError):
            hist_signal_single.at(timedelta(0), invalid="invalid")  # type: ignore[call-arg]

    def test_actual_fails_if_column_not_specified(self, hist_signal):
        with pytest.raises(ValueError):
            hist_signal.at(timedelta(0))

    def test_actual_fails_if_column_does_not_exist(self, hist_signal):
        with pytest.raises(ValueError):
            hist_signal.at(timedelta(0), "d")

    def test_actual_fails_if_negative_elapsed(self, hist_signal):
        with pytest.raises(ValueError):
            hist_signal.at(timedelta(seconds=-1), "a")

    def test_actual_fails_if_after_trace_end(self, hist_signal_single):
        with pytest.raises(ValueError):
            hist_signal_single.at(timedelta(hours=1, seconds=1))

    def test_actual_fails_if_at_is_none(self, hist_signal_single):
        with pytest.raises(ValueError):
            hist_signal_single.at(None)

    def test_datetime_index_requires_anchor(self):
        data = pd.Series([1, 2], index=pd.to_datetime(["2023-01-01", "2023-01-02"]))
        with pytest.raises(ValueError, match="anchor is required"):
            vs.Trace(data)

    def test_datetime_index_with_anchor_rebases(self):
        index = pd.to_datetime(
            [
                "2023-01-01 00:00:00",
                "2023-01-01 01:00:00",
                "2023-01-01 02:00:00",
            ]
        )
        data = pd.Series([10, 20, 30], index=index)
        trace = vs.Trace(data, anchor="2023-01-01 01:00:00")
        # Anchor row becomes elapsed=0; row before is dropped.
        assert trace.at(timedelta(0)) == 20
        assert trace.at(timedelta(hours=1)) == 30

    def test_datetime_index_anchor_must_match_existing_row(self):
        data = pd.Series(
            [1, 2],
            index=pd.to_datetime(["2023-01-01", "2023-01-02"]),
        )
        with pytest.raises(ValueError, match="not present in the data's index"):
            vs.Trace(data, anchor="2023-01-01 12:00:00")

    def test_anchor_forbidden_with_timedelta_index(self):
        data = pd.Series([1, 2], index=pd.to_timedelta(["0s", "1h"]))
        with pytest.raises(ValueError, match="only valid for datetime"):
            vs.Trace(data, anchor="2023-01-01")

    def test_anchor_forbidden_with_numeric_index(self):
        data = pd.Series([1, 2], index=[0, 3600])
        with pytest.raises(ValueError, match="only valid for datetime"):
            vs.Trace(data, anchor="2023-01-01")

    def test_timedelta_index_used_as_elapsed_offsets(self):
        # A TimedeltaIndex is interpreted directly: no normalization.
        data = pd.Series(
            [10, 20, 30],
            index=pd.to_timedelta(["0s", "30min", "1h"]),
        )
        trace = vs.Trace(data)
        assert trace.at(timedelta(0)) == 10
        assert trace.at(timedelta(minutes=30)) == 20
        assert trace.at(timedelta(hours=1)) == 30

    def test_strict_zero_start_rule(self):
        # Traces must start at elapsed=0.
        data = pd.Series([10, 20], index=pd.to_timedelta(["1h", "2h"]))
        with pytest.raises(ValueError, match="must start at offset=0"):
            vs.Trace(data)

    def test_numeric_index_interpreted_as_seconds(self):
        data = pd.Series([10, 20, 30], index=[0, 1800, 3600])
        trace = vs.Trace(data)
        assert trace.at(0) == 10
        assert trace.at(1800) == 20
        assert trace.at(3600) == 30

    def test_unsupported_on_overflow(self):
        index = pd.to_timedelta(["0s", "1h"])
        with pytest.raises(ValueError, match="not yet supported"):
            vs.Trace(pd.Series([1, 2], index=index), on_overflow="loop")  # type: ignore[arg-type]


def test_trace_views_share_immutable_data_and_sample_independently():
    trace = vs.Trace(pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]}, index=[0, 1, 2]))
    a, b = trace.select("a"), trace.select("b")
    assert a._offsets is trace._offsets
    assert b._offsets is trace._offsets
    assert [a.at(2), a.at(0), b.at(1), a.at(0.5)] == [3, 1, 5, 1]
    with pytest.raises(ValueError):
        a._offsets["a"][1][0] = 10
    with pytest.raises(ValueError):
        trace.select("missing")


@pytest.mark.parametrize("elapsed", [0.000001, 0.0000015, 0.1234567, 1.9999999, 2.0])
def test_trace_fractional_seconds_match_timedelta(elapsed):
    trace = vs.Trace(pd.Series([1, 2, 3], index=[0, 0.000002, 2]))
    assert trace.at(elapsed) == trace.at(timedelta(seconds=elapsed))


@pytest.mark.parametrize("fill_method", ["ffill", "bfill"])
def test_trace_bounds_apply_to_both_fill_methods(fill_method):
    trace = vs.Trace(pd.Series([10, 20], index=[0, 60]), fill_method=fill_method)
    assert trace.at(0) == 10
    assert trace.at(60) == 20
    assert trace.at(30) == (10 if fill_method == "ffill" else 20)
    for elapsed, boundary in [(-1, "before the start"), (61, "after the end")]:
        with pytest.raises(ValueError, match=boundary):
            trace.at(elapsed)


@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf])
def test_nonfinite_signal_inputs_fail_at_construction(value):
    with pytest.raises(ValueError, match="column 'load'.*offset"):
        vs.Trace(pd.Series([10, value], index=[0, 60], name="load"))
    trace = vs.Trace(pd.Series([10, 20], index=[0, 60]))
    with pytest.raises(ValueError, match="finite"):
        trace.at(value)


@pytest.mark.parametrize(
    "index", [[0, 0], [0, np.nan], [0, np.inf], pd.to_timedelta([0, None], unit="s")]
)
def test_trace_rejects_ambiguous_or_invalid_timestamps(index):
    with pytest.raises(ValueError, match="unique|missing|finite"):
        vs.Trace(pd.Series([10, 20], index=index))


def test_trace_rejects_empty_and_invalid_columns():
    for data in [
        pd.DataFrame(index=[0, 60]),
        pd.Series([np.nan], index=[0]),
        pd.DataFrame([[1, 2]], columns=["load", "load"], index=[0]),
    ]:
        with pytest.raises(ValueError):
            vs.Trace(data)
    with pytest.raises(ValueError, match="Available columns.*load"):
        vs.Trace(pd.Series([10], name="load", index=[0]), column="missing")


def test_csv_errors_identify_columns_and_timestamps(tmp_path):
    path = tmp_path / "load.csv"
    path.write_text("seconds,load\n0,10\n60,broken\n")
    with pytest.raises(ValueError, match="column 'load'.*numeric"):
        vs.Trace.from_csv(path)
    path.write_text("seconds,load\nyesterday-ish,10\n")
    with pytest.raises(ValueError, match="first column.*load.csv"):
        vs.Trace.from_csv(path)


def test_static_signal_returns_updated_value_at_any_time():
    signal = vs.StaticSignal(700)
    assert signal.at() == signal.at(60) == signal.at(timedelta(seconds=60)) == 700
    signal.set_value(500)
    assert signal.at(0) == 500


@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf, True, "700"])
def test_static_signal_rejects_invalid_values_without_mutation(value):
    with pytest.raises(ValueError, match="finite number"):
        vs.StaticSignal(value)
    signal = vs.StaticSignal(700)
    with pytest.raises(ValueError, match="finite number"):
        signal.set_value(value)
    assert signal.at() == 700
