import pandas as pd
import pytest
from datetime import timedelta

from vessim import TimeSeriesApi


class TestTraceSimulator:
    @pytest.fixture
    def time_series(self) -> TimeSeriesApi:
        index = [
            "2023-01-01T00:00:00",
            "2023-01-01T00:30:00",
            "2023-01-01T01:00:00",
        ]
        actual = pd.DataFrame({"a": [1, 2, 3], "b": [0, 3, 0]}, index=index)
        return TimeSeriesApi(actual)

    @pytest.fixture
    def time_series_single(self) -> TimeSeriesApi:
        index = ["2023-01-01T00:00:00", "2023-01-01T00:30:00", "2023-01-01T01:00:00"]
        actual = pd.Series([1, 2, 3], index=index)
        return TimeSeriesApi(actual, fill_method="bfill")

    @pytest.fixture
    def time_series_forecast(self) -> TimeSeriesApi:
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
        return TimeSeriesApi(actual, forecast)

    @pytest.fixture
    def time_series_static_forecast(self) -> TimeSeriesApi:
        index = pd.date_range("2023-01-01T00:00:00", "2023-01-01T03:00:00", freq="1H")
        actual = pd.Series([3, 2, 4, 0], index=index)
        forecast = pd.Series([4, 2, 4, 1], index=index)
        return TimeSeriesApi(actual, forecast)

    @pytest.mark.parametrize(
        "dt, expected",
        [
            (
                pd.to_datetime("2023-01-01T00:00:00"),
                pd.to_datetime("2023-01-01T00:30:00"),
            ),
            (
                pd.to_datetime("2023-01-01T00:10:00"),
                pd.to_datetime("2023-01-01T00:30:00"),
            ),
            (
                pd.to_datetime("2023-01-01T00:29:59"),
                pd.to_datetime("2023-01-01T00:30:00"),
            ),
            (
                pd.to_datetime("2023-01-01T00:40:00"),
                pd.to_datetime("2023-01-01T01:00:00"),
            ),
        ],
    )
    def test_next_update(self, time_series, dt, expected):
        assert time_series.next_update(dt) == expected

    def test_zones(self, time_series):
        assert time_series.zones() == ["a", "b"]

    def test_trace_actual_single_zone(self, time_series_single):
        assert time_series_single.actual("2023-01-01T00:45:00") == 3

    @pytest.mark.parametrize(
        "dt, zone, expected",
        [
            (pd.to_datetime("2023-01-01T00:00:00"), "a", 1),
            (pd.to_datetime("2023-01-01T00:00:10"), "a", 1),
            (pd.to_datetime("2023-01-01T01:00:00"), "a", 3),
            (pd.to_datetime("2023-01-01T10:00:00"), "a", 3),
            (pd.to_datetime("2023-01-01T00:29:59"), "b", 0),
            (pd.to_datetime("2023-01-01T00:30:00"), "b", 3),
        ],
    )
    def test_actual(self, time_series, dt, zone, expected):
        assert time_series.actual(dt, zone) == expected

    def test_actual_fails_if_zone_not_specified(self, time_series):
        with pytest.raises(ValueError):
            time_series.actual(pd.to_datetime("2023-01-01T00:00:00"))

    def test_actual_fails_if_zone_does_not_exist(self, time_series):
        with pytest.raises(ValueError):
            time_series.actual(pd.to_datetime("2023-01-01T00:00:00"), "c")

    def test_actual_fails_if_now_too_early(self, time_series):
        with pytest.raises(ValueError):
            time_series.actual(pd.to_datetime("2022-12-30T23:59:59"), "a")

    def test_actual_fails_if_now_too_late(self, time_series_single):
        with pytest.raises(ValueError):
            time_series_single.actual(pd.to_datetime("2023-01-01T01:00:01"))

    def test_forecast_single_zone(self, time_series_single):
        assert time_series_single.forecast(
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

    def test_forecast_static(self, time_series_static_forecast):
        assert time_series_static_forecast.forecast(
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
        "start, end, zone, expected",
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
        ],
    )
    def test_forecast(self, time_series_forecast, start, end, zone, expected):
        assert time_series_forecast.forecast(start, end, zone=zone).equals(expected)

    @pytest.mark.parametrize(
        "start, end, zone, frequency, method, expected",
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
                pd.tseries.offsets.DateOffset(minutes=35),
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
        self, time_series_forecast, start, end, zone, frequency, method, expected
    ):
        assert time_series_forecast.forecast(
            start,
            end,
            zone=zone,
            frequency=frequency,
            resample_method=method,
        ).equals(expected)

    def test_forecast_fails_if_zone_not_specified(self, time_series):
        with pytest.raises(ValueError):
            time_series.forecast(
                pd.to_datetime("2023-01-01T00:00:00"),
                pd.to_datetime("2023-01-01T01:00:00"),
            )

    def test_forecast_fails_if_zone_does_not_exist(self, time_series):
        with pytest.raises(ValueError):
            time_series.forecast(
                pd.to_datetime("2023-01-01T00:00:00"),
                pd.to_datetime("2023-01-01T01:00:00"),
                zone="c",
            )

    def test_forecast_fails_if_start_too_early(self, time_series):
        with pytest.raises(ValueError):
            time_series.forecast(
                pd.to_datetime("2022-12-31T23:59:59"),
                pd.to_datetime("2023-01-01T01:00:00"),
                zone="a",
            )

    def test_forecast_fails_with_invalid_frequency(self, time_series):
        with pytest.raises(ValueError):
            time_series.forecast(
                time_series.forecast(
                    pd.to_datetime("2023-01-01T00:00:00"),
                    pd.to_datetime("2023-01-01T01:00:00"),
                    zone="a",
                    frequency="invalid",
                )
            )

    def test_forecast_fails_if_not_enough_data_for_frequency(self, time_series):
        with pytest.raises(ValueError):
            time_series.forecast(
                pd.to_datetime("2023-01-01T00:00:00"),
                pd.to_datetime("2023-01-01T01:00:00"),
                zone="a",
                frequency="15T",
            )
