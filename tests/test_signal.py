import pytest
import pandas as pd
import numpy as np
from datetime import timedelta

import vessim as vs


class TestTrace:
    @pytest.fixture
    def hist_signal(self) -> vs.Trace:
        index = [
            "2023-01-01T00:00:00",
            "2023-01-01T00:30:00",
            "2023-01-01T01:00:00",
        ]
        actual = pd.DataFrame({"a": [1, 2, 3], "b": [0, 3, 0], "c": [None, 4, None]}, index=index)
        return vs.Trace(actual)

    @pytest.fixture
    def hist_signal_single(self) -> vs.Trace:
        index = ["2023-01-01T01:00:00", "2023-01-01T00:30:00", "2023-01-01T00:00:00"]
        actual = pd.Series([3, 2, 1], index=index)
        return vs.Trace(actual, fill_method="bfill")

    @pytest.fixture
    def hist_signal_forecast(self) -> vs.Trace:
        index = pd.date_range("2023-01-01T00:00:00", "2023-01-01T01:00:00", freq="20min")
        actual = pd.DataFrame({"a": [1, 5, 3, 2], "b": [0, 1, 2, 3]}, index=index)

        forecast_data = [
            ["2023-01-01T00:00:00", "2023-01-01T00:10:00", 2, 2.5],
            ["2023-01-01T00:00:00", "2023-01-01T01:00:00", 1.5, 2.5],
            ["2023-01-01T00:00:00", "2023-01-01T02:00:00", 2.5, 3.5],
            ["2023-01-01T00:00:00", "2023-01-01T03:00:00", 2, 1.5],
            ["2023-01-01T01:00:00", "2023-01-01T02:00:00", 3, 2.5],
            ["2023-01-01T01:00:00", "2023-01-01T03:00:00", 1.5, 1.5],
        ]
        forecast = pd.DataFrame(forecast_data, columns=["request_time", "forecast_time", "a", "b"])
        forecast.set_index(["request_time", "forecast_time"], inplace=True)
        return vs.Trace(actual, forecast)

    @pytest.fixture
    def hist_signal_static_forecast(self) -> vs.Trace:
        index = pd.date_range("2023-01-01T00:00:00", "2023-01-01T03:00:00", freq="1h")
        actual = pd.Series([3, 2, 4, 0], index=index)
        forecast = pd.Series([4, 2, 4, 1], index=index)
        return vs.Trace(actual, forecast)

    def test_columns(self, hist_signal):
        assert hist_signal.columns() == ["a", "b", "c"]

    def test_actual_single_column(self, hist_signal_single):
        assert hist_signal_single.now("2023-01-01T00:45:00") == 3

    def test_actual_none_values(self, hist_signal):
        assert hist_signal.now("2023-01-01T01:20:00", column="c") == 4

    @pytest.mark.parametrize(
        "dt, column, expected",
        [
            (("2023-01-01T00:00:00"), "a", 1),
            (("2023-01-01T00:00:10"), "a", 1),
            (("2023-01-01T01:00:00"), "a", 3),
            (("2023-01-01T10:00:00"), "a", 3),
            (("2023-01-01T00:29:59"), "b", 0),
            (("2023-01-01T00:30:00"), "b", 3),
        ],
    )
    def test_actual(self, hist_signal, dt, column, expected):
        assert hist_signal.now(dt, column) == expected

    def test_actual_fails_if_invalid_key_word_arguments(self, hist_signal_single):
        with pytest.raises(ValueError):
            hist_signal_single.now("2023-01-01T00:00:00", invalid="invalid")

    def test_actual_fails_if_column_not_specified(self, hist_signal):
        with pytest.raises(ValueError):
            hist_signal.now("2023-01-01T00:00:00")

    def test_actual_fails_if_column_does_not_exist(self, hist_signal):
        with pytest.raises(ValueError):
            hist_signal.now("2023-01-01T00:00:00", "d")

    def test_actual_fails_if_now_too_early(self, hist_signal):
        with pytest.raises(ValueError):
            hist_signal.now("2022-12-30T23:59:59", "a")

    def test_actual_fails_if_now_too_late(self, hist_signal_single):
        with pytest.raises(ValueError):
            hist_signal_single.now("2023-01-01T01:00:01")

    def test_forecast_single_column(self, hist_signal_single):
        assert hist_signal_single.forecast(
            start_time="2023-01-01T00:00:00",
            end_time="2023-01-01T01:00:00",
        ) == {
            np.datetime64("2023-01-01T00:30:00.000000000"): 2.0,  # type: ignore
            np.datetime64("2023-01-01T01:00:00.000000000"): 3.0,  # type: ignore
        }

    def test_forecast_static(self, hist_signal_static_forecast):
        assert hist_signal_static_forecast.forecast(
            start_time="2023-01-01T00:00:00",
            end_time="2023-01-01T02:00:00",
        ) == {
            np.datetime64("2023-01-01T01:00:00.000000000"): 2.0,  # type: ignore
            np.datetime64("2023-01-01T02:00:00.000000000"): 4.0,  # type: ignore
        }

    @pytest.mark.parametrize(
        "start, end, column, expected",
        [
            (
                "2023-01-01T00:00:00",
                "2023-01-01T01:00:00",
                "a",
                {
                    np.datetime64("2023-01-01T00:10:00.000000000"): 2.0,  # type: ignore
                    np.datetime64("2023-01-01T01:00:00.000000000"): 1.5,  # type: ignore
                },
            ),
            (
                "2023-01-01T01:00:00",
                "2023-01-01T02:00:00",
                "a",
                {np.datetime64("2023-01-01T02:00:00.000000000"): 3.0},  # type: ignore
            ),
            (
                "2023-01-01T00:05:00",
                "2023-01-01T00:50:00",
                "a",
                {np.datetime64("2023-01-01T00:10:00.000000000"): 2.0},  # type: ignore
            ),
            (
                "2023-01-01T00:11:00",
                "2023-01-01T00:59:00",
                "a",
                {},
            ),
            (
                "2023-01-01T00:00:00",
                "2023-01-01T02:00:00",
                "b",
                {
                    np.datetime64("2023-01-01T00:10:00.000000000"): 2.5,  # type: ignore
                    np.datetime64("2023-01-01T01:00:00.000000000"): 2.5,  # type: ignore
                    np.datetime64("2023-01-01T02:00:00.000000000"): 3.5,  # type: ignore
                },
            ),
            (
                "2023-01-01T01:00:00",
                "2023-04-04T14:00:00",
                "a",
                {
                    np.datetime64("2023-01-01T02:00:00.000000000"): 3.0,  # type: ignore
                    np.datetime64("2023-01-01T03:00:00.000000000"): 1.5,  # type: ignore
                },
            ),
        ],
    )
    def test_forecast(self, hist_signal_forecast, start, end, column, expected):
        assert hist_signal_forecast.forecast(start, end, column) == expected

    @pytest.mark.parametrize(
        "start, end, column, frequency, method, expected",
        [
            (
                "2023-01-01T00:00:00",
                "2023-01-01T03:00:00",
                "a",
                "2h",
                None,
                {np.datetime64("2023-01-01T02:00:00.000000000"): 2.5},  # type: ignore
            ),
            (
                "2023-01-01T00:00:00",
                "2023-01-01T01:00:00",
                "b",
                timedelta(minutes=35),
                "bfill",
                {np.datetime64("2023-01-01T00:35:00.000000000"): 2.5},  # type: ignore
            ),
            (
                "2023-01-01T01:00:00",
                "2023-01-01T04:00:00",
                "a",
                timedelta(minutes=45),
                "ffill",
                {
                    np.datetime64("2023-01-01T01:45:00.000000000"): 2.0,  # type: ignore
                    np.datetime64("2023-01-01T02:30:00.000000000"): 3.0,  # type: ignore
                    np.datetime64("2023-01-01T03:15:00.000000000"): 1.5,  # type: ignore
                    np.datetime64("2023-01-01T04:00:00.000000000"): 1.5,  # type: ignore
                },
            ),
            (
                "2023-01-01T00:00:00",
                "2023-01-01T05:00:00",
                "a",
                timedelta(hours=1, minutes=30),
                "linear",
                {
                    np.datetime64("2023-01-01T01:30:00.000000000"): 2.0,  # type: ignore
                    np.datetime64("2023-01-01T03:00:00.000000000"): 2.0,  # type: ignore
                    np.datetime64("2023-01-01T04:30:00.000000000"): 2.0,  # type: ignore
                },
            ),
            (
                "2023-01-01T00:20:00",
                "2023-01-01T01:00:00",
                "b",
                "20min",
                "bfill",
                {
                    np.datetime64("2023-01-01T00:40:00.000000000"): 2.5,  # type: ignore
                    np.datetime64("2023-01-01T01:00:00.000000000"): 2.5,  # type: ignore
                },
            ),
            (
                "2023-01-01T00:30:00",
                "2023-01-01T01:00:00",
                "b",
                "20min",
                "linear",
                {np.datetime64("2023-01-01T00:50:00.000000000"): 2.0},  # type: ignore
            ),
            (
                "2023-01-01T00:45:00",
                "2023-01-01T01:00:00",
                "b",
                "12min",
                "linear",
                {np.datetime64("2023-01-01T00:57:00.000000000"): 2.4},  # type: ignore
            ),
            (
                "2023-01-01T00:35:00",
                "2023-01-01T00:40:00",
                "a",
                "5min",
                "linear",
                {np.datetime64("2023-01-01T00:40:00.000000000"): 4.3},  # type: ignore
            ),
            (
                "2023-01-01T00:40:00",
                "2023-01-01T00:55:00",
                "b",
                "5min",
                "nearest",
                {
                    np.datetime64("2023-01-01T00:45:00.000000000"): 2.0,  # type: ignore
                    np.datetime64("2023-01-01T00:50:00.000000000"): 2.0,  # type: ignore
                    np.datetime64("2023-01-01T00:55:00.000000000"): 2.5,  # type: ignore
                },
            ),
            (
                "2023-01-01T01:00:00",
                "2023-01-01T04:00:00",
                "b",
                "1h",
                "bfill",
                {
                    np.datetime64("2023-01-01T02:00:00.000000000"): 2.5,  # type: ignore
                    np.datetime64("2023-01-01T03:00:00.000000000"): 1.5,  # type: ignore
                    np.datetime64("2023-01-01T04:00:00.000000000"): np.nan,  # type: ignore
                },
            ),
            (
                "2023-01-01T01:00:00",
                "2023-01-01T04:00:00",
                "b",
                "1h",
                "nearest",
                {
                    np.datetime64("2023-01-01T02:00:00.000000000"): 2.5,  # type: ignore
                    np.datetime64("2023-01-01T03:00:00.000000000"): 1.5,  # type: ignore
                    np.datetime64("2023-01-01T04:00:00.000000000"): 1.5,  # type: ignore
                },
            ),
        ],
    )
    def test_forecast_with_frequency(
        self, hist_signal_forecast, start, end, column, frequency, method, expected
    ):
        forecast = hist_signal_forecast.forecast(
            start,
            end,
            column=column,
            frequency=frequency,
            resample_method=method,
        )
        # Complicated because np.nan == np.nan is False
        assert forecast.keys() == expected.keys()
        assert all(
            np.isnan(expected[k]) if np.isnan(forecast[k]) else forecast[k] == expected[k]
            for k in forecast.keys()
        )

    def test_forecast_fails_if_column_not_specified(self, hist_signal):
        with pytest.raises(ValueError):
            hist_signal.forecast(
                "2023-01-01T00:00:00",
                "2023-01-01T01:00:00",
            )

    def test_forecast_fails_if_column_does_not_exist(self, hist_signal):
        with pytest.raises(ValueError):
            hist_signal.forecast(
                "2023-01-01T00:00:00",
                "2023-01-01T01:00:00",
                column="d",
            )

    def test_forecast_fails_if_start_too_early(self, hist_signal_forecast):
        with pytest.raises(ValueError):
            hist_signal_forecast.forecast(
                "2022-12-31T23:59:59",
                "2023-01-01T01:00:00",
                column="a",
            )

    def test_forecast_fails_with_invalid_frequency(self, hist_signal):
        with pytest.raises(ValueError):
            hist_signal.forecast(
                hist_signal.forecast(
                    "2023-01-01T00:00:00",
                    "2023-01-01T01:00:00",
                    column="a",
                    frequency="invalid",
                )
            )

    def test_forecast_fails_if_not_enough_data_for_frequency(self, hist_signal):
        with pytest.raises(ValueError):
            hist_signal.forecast(
                "2023-01-01T00:00:00",
                "2023-01-01T01:00:00",
                column="a",
                frequency="15min",
            )
