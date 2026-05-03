from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

import vessim as vs


class TestTrace:
    @pytest.fixture
    def hist_signal(self) -> vs.Trace:
        index = pd.to_datetime([
            "2023-01-01T00:00:00",
            "2023-01-01T00:30:00",
            "2023-01-01T01:00:00",
        ])
        actual = pd.DataFrame(
            {"a": [1, 2, 3], "b": [0, 3, 0], "c": [None, 4, None]},
            index=index - index[0]
        )
        return vs.Trace(actual)

    @pytest.fixture
    def hist_signal_single(self) -> vs.Trace:
        index = pd.to_datetime([
            "2023-01-01T01:00:00",
            "2023-01-01T00:30:00",
            "2023-01-01T00:00:00"
        ])
        actual = pd.Series([3, 2, 1], index=index - index.min())
        return vs.Trace(actual, fill_method="bfill")

    def test_columns(self, hist_signal):
        assert hist_signal.columns() == ["a", "b", "c"]

    def test_actual_single_column(self, hist_signal_single):
        assert hist_signal_single.at(timedelta(minutes=45)) == 3

    def test_actual_none_values(self, hist_signal):
        assert hist_signal.at(timedelta(hours=1, minutes=20), column="c") == 4

    @pytest.mark.parametrize(
        "elapsed, column, expected",
        [
            (timedelta(0), "a", 1),
            (timedelta(seconds=10), "a", 1),
            (timedelta(hours=1), "a", 3),
            (timedelta(hours=10), "a", 3),
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
        data = pd.Series(
            [1, 2], index=pd.to_datetime(["2023-01-01", "2023-01-02"])
        )
        with pytest.raises(ValueError, match="anchor is required"):
            vs.Trace(data)

    def test_datetime_index_with_anchor_rebases(self):
        index = pd.to_datetime([
            "2023-01-01 00:00:00",
            "2023-01-01 01:00:00",
            "2023-01-01 02:00:00",
        ])
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
        with pytest.raises(ValueError, match="must start at elapsed=0"):
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


class TestStaticSignal:
    def test_returns_value(self):
        s = vs.StaticSignal(42)
        assert s.at() == 42
        assert s.at(timedelta(hours=5)) == 42
        assert s.at(60) == 42  # int seconds

    def test_set_value(self):
        s = vs.StaticSignal(1)
        s.set_value(7)
        assert s.at() == 7
