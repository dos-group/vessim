import pytest
import pandas as pd
from datetime import timedelta

from vessim.signal import HistoricalSignal


class TestHistoricalSignal:
    @pytest.fixture
    def hist_signal(self) -> HistoricalSignal:
        index = [
            "2023-01-01T00:00:00",
            "2023-01-01T00:30:00",
            "2023-01-01T01:00:00",
        ]
        actual = pd.DataFrame(
            {"a": [1, 2, 3], "b": [0, 3, 0], "c":[None, 4, None]}, index=index
        )
        return HistoricalSignal(actual)

    @pytest.fixture
    def hist_signal_single(self) -> HistoricalSignal:
        index = ["2023-01-01T01:00:00", "2023-01-01T00:30:00", "2023-01-01T00:00:00"]
        actual = pd.Series([3, 2, 1], index=index)
        return HistoricalSignal(actual, fill_method="bfill")

    @pytest.fixture
    def hist_signal_forecast(self) -> HistoricalSignal:
        index = pd.date_range("2023-01-01T00:00:00", "2023-01-01T01:00:00", freq="20T")
        actual = pd.DataFrame(
            {"a": [1, 5, 3, 2], "b": [0, 1, 2, 3], "c": [4, 3, 2, 7]}, index=index
        )

        forecast_data = [
            ["2023-01-01T00:00:00", "2023-01-01T00:10:00", 2, 2.5],
            ["2023-01-01T00:00:00", "2023-01-01T01:00:00", 1.5, 2.5],
            ["2023-01-01T00:00:00", "2023-01-01T02:00:00", 2.5, 3.5],
            ["2023-01-01T00:00:00", "2023-01-01T03:00:00", 2, 1.5],
            ["2023-01-01T01:00:00", "2023-01-01T02:00:00", 3, 2.5],
            ["2023-01-01T01:00:00", "2023-01-01T03:00:00", 1.5, 1.5],
        ]
        forecast = pd.DataFrame(
            forecast_data, columns=["request_time", "forecast_time", "a", "b"]
        )
        forecast.set_index(["request_time", "forecast_time"], inplace=True)
        return HistoricalSignal(actual, forecast)

    @pytest.fixture
    def hist_signal_static_forecast(self) -> HistoricalSignal:
        index = pd.date_range("2023-01-01T00:00:00", "2023-01-01T03:00:00", freq="1H")
        actual = pd.Series([3, 2, 4, 0], index=index)
        forecast = pd.Series([4, 2, 4, 1], index=index)
        return HistoricalSignal(actual, forecast)

    def test_columns(self, hist_signal):
        assert hist_signal.columns() == ["a", "b", "c"]

    def test_actual_single_column(self, hist_signal_single):
        assert hist_signal_single.at("2023-01-01T00:45:00") == 3

    def test_actual_none_values(self, hist_signal):
        assert hist_signal.at("2023-01-01T01:20:00", column="c") == 4

    @pytest.mark.parametrize(
        "dt, column, expected",
        [
            (pd.to_datetime("2023-01-01T00:00:00"), "a", 1),
            (pd.to_datetime("2023-01-01T00:00:10"), "a", 1),
            (pd.to_datetime("2023-01-01T01:00:00"), "a", 3),
            (pd.to_datetime("2023-01-01T10:00:00"), "a", 3),
            (pd.to_datetime("2023-01-01T00:29:59"), "b", 0),
            (pd.to_datetime("2023-01-01T00:30:00"), "b", 3),
        ],
    )
    def test_actual(self, hist_signal, dt, column, expected):
        assert hist_signal.at(dt, column) == expected

    def test_actual_fails_if_column_not_specified(self, hist_signal):
        with pytest.raises(ValueError):
            hist_signal.at(pd.to_datetime("2023-01-01T00:00:00"))

    def test_actual_fails_if_column_does_not_exist(self, hist_signal):
        with pytest.raises(ValueError):
            hist_signal.at(pd.to_datetime("2023-01-01T00:00:00"), "d")

    def test_actual_fails_if_now_too_early(self, hist_signal):
        with pytest.raises(ValueError):
            hist_signal.at(pd.to_datetime("2022-12-30T23:59:59"), "a")

    def test_actual_fails_if_now_too_late(self, hist_signal_single):
        with pytest.raises(ValueError):
            hist_signal_single.at(pd.to_datetime("2023-01-01T01:00:01"))

    def test_forecast_single_column(self, hist_signal_single):
        assert hist_signal_single.forecast(
            start_time="2023-01-01T00:00:00",
            end_time="2023-01-01T01:00:00",
        ).equals(
            pd.Series(
                [2, 3],
                index=[
                    pd.to_datetime("2023-01-01T00:30:00"),
                    pd.to_datetime("2023-01-01T01:00:00"),
                ],
            )
        )

    def test_forecast_static(self, hist_signal_static_forecast):
        assert hist_signal_static_forecast.forecast(
            start_time="2023-01-01T00:00:00",
            end_time="2023-01-01T02:00:00",
        ).equals(
            pd.Series(
                [2, 4],
                index=[
                    pd.to_datetime("2023-01-01T01:00:00"),
                    pd.to_datetime("2023-01-01T02:00:00"),
                ],
            )
        )

    @pytest.mark.parametrize(
        "start, end, column, expected",
        [
            (
                "2023-01-01T00:00:00",
                "2023-01-01T01:00:00",
                "a",
                pd.Series(
                    [2.0, 1.5],
                    index=[
                        pd.to_datetime("2023-01-01T00:10:00"),
                        pd.to_datetime("2023-01-01T01:00:00"),
                    ],
                ),
            ),
            (
                "2023-01-01T01:00:00",
                "2023-01-01T02:00:00",
                "a",
                pd.Series([3.0], index=[pd.to_datetime("2023-01-01T02:00:00")]),
            ),
            (
                "2023-01-01T00:05:00",
                "2023-01-01T00:50:00",
                "a",
                pd.Series([2.0], index=[pd.to_datetime("2023-01-01T00:10:00")]),
            ),
            (
                "2023-01-01T00:11:00",
                "2023-01-01T00:59:00",
                "a",
                pd.Series([], dtype=float, index=pd.DatetimeIndex([])),
            ),
            (
                "2023-01-01T00:00:00",
                "2023-01-01T02:00:00",
                "b",
                pd.Series(
                    [2.5, 2.5, 3.5],
                    index=[
                        pd.to_datetime("2023-01-01T00:10:00"),
                        pd.to_datetime("2023-01-01T01:00:00"),
                        pd.to_datetime("2023-01-01T02:00:00"),
                    ],
                ),
            ),
            (
                "2023-01-01T01:00:00",
                "2023-04-04T14:00:00",
                "a",
                pd.Series(
                    [3.0, 1.5],
                    index=[
                        pd.to_datetime("2023-01-01T02:00:00"),
                        pd.to_datetime("2023-01-01T03:00:00"),
                    ],
                ),
            ),
        ],
    )
    def test_forecast(self, hist_signal_forecast, start, end, column, expected):
        assert hist_signal_forecast.forecast(start, end, column).equals(expected)

    @pytest.mark.parametrize(
        "start, end, column, frequency, method, expected",
        [
            (
                "2023-01-01T00:00:00",
                "2023-01-01T03:00:00",
                "a",
                "2H",
                None,
                pd.Series([2.5], index=[pd.to_datetime("2023-01-01T02:00:00")]),
            ),
            (
                "2023-01-01T00:00:00",
                "2023-01-01T01:00:00",
                "b",
                timedelta(minutes=35),
                "bfill",
                pd.Series([2.5], index=[pd.to_datetime("2023-01-01T00:35:00")]),
            ),
            (
                "2023-01-01T01:00:00",
                "2023-01-01T03:00:00",
                "a",
                timedelta(minutes=45),
                "ffill",
                pd.Series(
                    [2.0, 3.0],
                    index=[
                        pd.to_datetime("2023-01-01T01:45:00"),
                        pd.to_datetime("2023-01-01T02:30:00"),
                    ],
                ),
            ),
            (
                "2023-01-01T00:00:00",
                "2023-01-01T03:00:00",
                "a",
                timedelta(hours=1, minutes=30),
                "time",
                pd.Series(
                    [2.0, 2.0],
                    index=[
                        pd.to_datetime("2023-01-01T01:30:00"),
                        pd.to_datetime("2023-01-01T03:00:00"),
                    ],
                ),
            ),
            (
                "2023-01-01T00:20:00",
                "2023-01-01T01:00:00",
                "b",
                "20T",
                "bfill",
                pd.Series(
                    [2.5, 2.5],
                    index=[
                        pd.to_datetime("2023-01-01T00:40:00"),
                        pd.to_datetime("2023-01-01T01:00:00"),
                    ],
                ),
            ),
            (
                "2023-01-01T00:30:00",
                "2023-01-01T01:00:00",
                "b",
                "20T",
                "time",
                pd.Series(
                    [2.0],
                    index=[pd.to_datetime("2023-01-01T00:50:00")],
                ),
            ),
            (
                "2023-01-01T00:45:00",
                "2023-01-01T01:00:00",
                "b",
                "12T",
                "time",
                pd.Series([2.4], index=[pd.to_datetime("2023-01-01T00:57:00")]),
            ),
            (
                "2023-01-01T00:35:00",
                "2023-01-01T00:40:00",
                "a",
                "5T",
                "time",
                pd.Series([4.3], index=[pd.to_datetime("2023-01-01T00:40:00")]),
            ),
        ],
    )
    def test_forecast_with_frequency(
        self, hist_signal_forecast, start, end, column, frequency, method, expected
    ):
        assert hist_signal_forecast.forecast(
            start,
            end,
            column=column,
            frequency=frequency,
            resample_method=method,
        ).equals(expected)

    def test_forecast_fails_if_column_not_specified(self, hist_signal):
        with pytest.raises(ValueError):
            hist_signal.forecast(
                pd.to_datetime("2023-01-01T00:00:00"),
                pd.to_datetime("2023-01-01T01:00:00"),
            )

    def test_forecast_fails_if_column_does_not_exist(self, hist_signal):
        with pytest.raises(ValueError):
            hist_signal.forecast(
                pd.to_datetime("2023-01-01T00:00:00"),
                pd.to_datetime("2023-01-01T01:00:00"),
                column="d",
            )

    def test_forecast_fails_if_start_too_early(self, hist_signal_forecast):
        with pytest.raises(ValueError):
            hist_signal_forecast.forecast(
                pd.to_datetime("2022-12-31T23:59:59"),
                pd.to_datetime("2023-01-01T01:00:00"),
                column="a",
            )

    def test_forecast_fails_with_invalid_frequency(self, hist_signal):
        with pytest.raises(ValueError):
            hist_signal.forecast(
                hist_signal.forecast(
                    pd.to_datetime("2023-01-01T00:00:00"),
                    pd.to_datetime("2023-01-01T01:00:00"),
                    column="a",
                    frequency="invalid",
                )
            )

    def test_forecast_fails_if_not_enough_data_for_frequency(self, hist_signal):
        with pytest.raises(ValueError):
            hist_signal.forecast(
                pd.to_datetime("2023-01-01T00:00:00"),
                pd.to_datetime("2023-01-01T01:00:00"),
                column="a",
                frequency="15T",
            )
