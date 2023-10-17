import pandas as pd
import pytest
from datetime import timedelta

from vessim import TimeSeriesApi


class TestTraceSimulator:
    @pytest.fixture
    def trace_sim(self) -> TimeSeriesApi:
        index = [
            pd.to_datetime("2023-01-01T00:00:00"),
            pd.to_datetime("2023-01-01T00:30:00"),
            pd.to_datetime("2023-01-01T01:00:00"),
        ]
        actual = pd.DataFrame({"a": [1, 2, 3], "b": [0, 3, 0]}, index=index)
        return TimeSeriesApi(actual)

    @pytest.fixture
    def trace_sim_series(self) -> TimeSeriesApi:
        index = [
            pd.to_datetime("2023-01-01T00:00:00"),
            pd.to_datetime("2023-01-01T00:30:00"),
            pd.to_datetime("2023-01-01T01:00:00"),
        ]
        actual = pd.Series([1, 2, 3], index=index)
        return TimeSeriesApi(actual)

    @pytest.fixture
    def trace_sim_forecast(self) -> TimeSeriesApi:
        index = [
            pd.to_datetime("2023-01-01T00:00:00"),
            pd.to_datetime("2023-01-01T01:00:00"),
        ]
        actual = pd.DataFrame({"a": [1, 2], "b": [0, 3]}, index=index)
        forecast_data = [
            ["2023-01-01T00:00:00", "2023-01-01T01:00:00", 1.5, 3],
            ["2023-01-01T00:00:00", "2023-01-01T02:00:00", 2.5, 3.5],
            ["2023-01-01T00:00:00", "2023-01-01T03:00:00", 2, 1.5],
            ["2023-01-01T01:00:00", "2023-01-01T02:00:00", 3, 2.5],
            ["2023-01-01T01:00:00", "2023-01-01T03:00:00", 1.5, 1.5],
        ]
        forecast = pd.DataFrame(
            forecast_data, columns=["request_time", "forecast_time", "a", "b"]
        )
        forecast["request_time"] = pd.to_datetime(forecast["request_time"])
        forecast["forecast_time"] = pd.to_datetime(forecast["forecast_time"])
        forecast.set_index(["request_time", "forecast_time"], inplace=True)
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
    def test_next_update(self, trace_sim, dt, expected):
        assert trace_sim.next_update(dt) == expected

    def test_zones(self, trace_sim):
        assert trace_sim.zones() == ["a", "b"]

    def test_trace_actual_at_single_zone(self, trace_sim_series):
        assert trace_sim_series.actual("2023-01-01T00:00:00") == 1

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
    def test_actual_at(self, trace_sim, dt, zone, expected):
        assert trace_sim.actual(dt, zone) == expected

    def test_actual_at_fails_if_zone_not_specified(self, trace_sim):
        with pytest.raises(ValueError):
            trace_sim.actual(pd.to_datetime("2023-01-01T00:00:00"))

    def test_actual_at_fails_if_zone_does_not_exist(self, trace_sim):
        with pytest.raises(ValueError):
            trace_sim.actual(pd.to_datetime("2023-01-01T00:00:00"), "c")

    def test_actual_at_fails_if_now_too_early(self, trace_sim):
        with pytest.raises(ValueError):
            trace_sim.actual(pd.to_datetime("2022-12-30T23:59:59"), "a")

    def test_forecast_at_single_zone(self, trace_sim_series):
        assert trace_sim_series.forecast(
            start_time=pd.to_datetime("2023-01-01T00:00:00"),
            end_time=pd.to_datetime("2023-01-01T01:00:00"),
        ).equals(
            pd.Series(
                [2, 3],
                index=[
                    pd.to_datetime("2023-01-01T00:30:00"),
                    pd.to_datetime("2023-01-01T01:00:00"),
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
                pd.Series([1.5], index=[pd.to_datetime("2023-01-01T01:00:00")]),
            ),
            (
                "2023-01-01T01:00:00",
                "2023-01-01T02:00:00",
                "a",
                pd.Series([3.0], index=[pd.to_datetime("2023-01-01T02:00:00")]),
            ),
            (
                "2023-01-01T00:10:00",
                "2023-01-01T01:00:00",
                "a",
                pd.Series([1.5], index=[pd.to_datetime("2023-01-01T01:00:00")]),
            ),
            (
                "2023-01-01T00:00:00",
                "2023-01-01T00:40:00",
                "a",
                pd.Series([], dtype=float, index=pd.DatetimeIndex([])),
            ),
            (
                "2023-01-01T00:00:00",
                "2023-01-01T02:00:00",
                "b",
                pd.Series(
                    [3, 3.5],
                    index=[
                        pd.to_datetime("2023-01-01T01:00:00"),
                        pd.to_datetime("2023-01-01T02:00:00"),
                    ],
                ),
            ),
        ],
    )
    def test_forecast_at(self, trace_sim_forecast, start, end, zone, expected):
        assert trace_sim_forecast.forecast(
            pd.to_datetime(start), pd.to_datetime(end), zone=zone
        ).equals(expected)

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
                pd.Series([3.0], index=[pd.to_datetime("2023-01-01T00:35:00")]),
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
                    [3.0, 3.0],
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
                    [2.5],
                    index=[pd.to_datetime("2023-01-01T00:50:00")],
                ),
            ),
        ],
    )
    def test_forecast_at_with_frequency(
        self, trace_sim_forecast, start, end, zone, frequency, method, expected
    ):
        assert trace_sim_forecast.forecast(
            pd.to_datetime(start),
            pd.to_datetime(end),
            zone=zone,
            frequency=frequency,
            resample_method=method,
        ).equals(expected)

    def test_forecast_at_fails_if_zone_not_specified(self, trace_sim):
        with pytest.raises(ValueError):
            trace_sim.forecast(
                pd.to_datetime("2023-01-01T00:00:00"),
                pd.to_datetime("2023-01-01T01:00:00"),
            )

    def test_forecast_at_fails_if_zone_does_not_exist(self, trace_sim):
        with pytest.raises(ValueError):
            trace_sim.forecast(
                pd.to_datetime("2023-01-01T00:00:00"),
                pd.to_datetime("2023-01-01T01:00:00"),
                zone="c",
            )

    def test_forecast_at_fails_if_start_too_early(self, trace_sim):
        with pytest.raises(ValueError):
            trace_sim.forecast(
                pd.to_datetime("2022-12-31T23:59:59"),
                pd.to_datetime("2023-01-01T01:00:00"),
                zone="a",
            )

    def test_forecast_at_fails_with_invalid_frequency(self, trace_sim):
        with pytest.raises(ValueError):
            trace_sim.forecast(
                trace_sim.forecast(
                pd.to_datetime("2023-01-01T00:00:00"),
                pd.to_datetime("2023-01-01T01:00:00"),
                zone="a",
                frequency="invalid",
            )
            )

    def test_forecast_at_fails_if_not_enough_data_for_frequency(self, trace_sim):
        with pytest.raises(ValueError):
            trace_sim.forecast(
                pd.to_datetime("2023-01-01T00:00:00"),
                pd.to_datetime("2023-01-01T01:00:00"),
                zone="a",
                frequency="15T",
            )
