from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

import vessim as vs


class TestTrace:
    @pytest.fixture
    def hist_signal(self) -> vs.Trace:
        index = [
            "2023-01-01T00:00:00",
            "2023-01-01T00:30:00",
            "2023-01-01T01:00:00",
        ]
        actual = pd.DataFrame(
            {"a": [1, 2, 3], "b": [0, 3, 0], "c": [None, 4, None]}, index=index
        )
        return vs.Trace.from_datetime(actual)

    @pytest.fixture
    def hist_signal_single(self) -> vs.Trace:
        index = ["2023-01-01T01:00:00", "2023-01-01T00:30:00", "2023-01-01T00:00:00"]
        actual = pd.Series([3, 2, 1], index=index)
        return vs.Trace.from_datetime(actual, fill_method="bfill")

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

    def test_offset_shifts_trace(self):
        index = pd.date_range("2023-01-01T00:00:00", periods=3, freq="1h")
        actual = pd.Series([1, 2, 3], index=index)
        trace = vs.Trace.from_datetime(actual, offset=timedelta(hours=2))
        # First row now lives at elapsed=2h instead of elapsed=0
        with pytest.raises(ValueError):
            trace.at(timedelta(hours=1))
        assert trace.at(timedelta(hours=2)) == 1
        assert trace.at(timedelta(hours=3, minutes=30)) == 2

    def test_from_datetime_normalizes_calendar_dates(self):
        # Two traces with different calendar starts produce identical lookups.
        a = pd.Series(
            [10, 20], index=pd.to_datetime(["2022-06-09T00:00", "2022-06-09T01:00"])
        )
        b = pd.Series(
            [10, 20], index=pd.to_datetime(["2024-12-31T00:00", "2024-12-31T01:00"])
        )
        ta, tb = vs.Trace.from_datetime(a), vs.Trace.from_datetime(b)
        for elapsed in (timedelta(0), timedelta(minutes=30), timedelta(hours=1)):
            assert ta.at(elapsed) == tb.at(elapsed)

    def test_init_rejects_datetime_index_with_pointer(self):
        data = pd.Series(
            [1, 2], index=pd.to_datetime(["2023-01-01", "2023-01-02"])
        )
        with pytest.raises(TypeError, match="from_datetime"):
            vs.Trace(data)

    def test_timedelta_index_used_as_elapsed_offsets(self):
        # A TimedeltaIndex is interpreted directly — no normalization.
        data = pd.Series(
            [10, 20, 30],
            index=pd.to_timedelta(["0s", "30min", "1h"]),
        )
        trace = vs.Trace(data)
        assert trace.at(timedelta(0)) == 10
        assert trace.at(timedelta(minutes=30)) == 20
        assert trace.at(timedelta(hours=1)) == 30

    def test_timedelta_index_preserves_nonzero_start(self):
        # If the user's offsets don't start at 0, that's their declared start —
        # we don't normalize it away (use offset= for an additional shift).
        data = pd.Series([10, 20], index=pd.to_timedelta(["1h", "2h"]))
        trace = vs.Trace(data)
        with pytest.raises(ValueError):
            trace.at(timedelta(minutes=30))
        assert trace.at(timedelta(hours=1)) == 10
        assert trace.at(timedelta(hours=2)) == 20

    def test_numeric_index_interpreted_as_seconds(self):
        data = pd.Series([10, 20, 30], index=[0, 1800, 3600])
        trace = vs.Trace(data)
        assert trace.at(0) == 10
        assert trace.at(1800) == 20
        assert trace.at(3600) == 30

    def test_unsupported_on_overflow(self):
        index = pd.date_range("2023-01-01", periods=2, freq="1h")
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
