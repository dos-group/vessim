import pandas as pd
import pytest

from vessim.core.simulator import CarbonApi, Generator, TraceSimulator


class TestTraceSimulator:

    @pytest.fixture
    def trace_sim(self) -> TraceSimulator:
        index = [
            pd.to_datetime("2023-01-01T00:00:00"),
            pd.to_datetime("2023-01-01T00:30:00"),
            pd.to_datetime("2023-01-01T01:00:00")
        ]
        actual = pd.DataFrame({"a": [1, 2, 3], "b": [0, 3, 0]}, index=index)
        return TraceSimulator(actual)

    @pytest.fixture
    def trace_sim_series(self) -> TraceSimulator:
        index = [
            pd.to_datetime("2023-01-01T00:00:00"),
            pd.to_datetime("2023-01-01T00:30:00"),
            pd.to_datetime("2023-01-01T01:00:00")
        ]
        actual = pd.Series([1, 2, 3], index=index)
        return TraceSimulator(actual)

    @pytest.fixture
    def trace_sim_forecast(self) -> TraceSimulator:
        index = [
            pd.to_datetime("2023-01-01T00:00:00"),
            pd.to_datetime("2023-01-01T01:00:00")
        ]
        actual = pd.DataFrame({"a": [1, 2], "b": [0, 3]}, index=index)
        forecast = pd.DataFrame({
            "a": [
                {
                    pd.to_datetime("2023-01-01T01:00:00"): 1.5,
                    pd.to_datetime("2023-01-01T02:00:00"): 3,
                },
                {
                    pd.to_datetime("2023-01-01T02:00:00"): 1.5,
                    pd.to_datetime("2023-01-01T03:00:00"): 3,
                },
            ],
            "b": [
                {
                    pd.to_datetime("2023-01-01T01:00:00"): 3,
                    pd.to_datetime("2023-01-01T02:00:00"): 2.5,
                },
                {
                    pd.to_datetime("2023-01-01T02:00:00"): 2,
                    pd.to_datetime("2023-01-01T03:00:00"): 1.5,
                },
            ],
        }, index=index)
        return TraceSimulator(actual, forecast)

    @pytest.mark.parametrize("dt, expected", [
        (pd.to_datetime("2023-01-01T00:00:00"), pd.to_datetime("2023-01-01T00:30:00")),
        (pd.to_datetime("2023-01-01T00:10:00"), pd.to_datetime("2023-01-01T00:30:00")),
        (pd.to_datetime("2023-01-01T00:29:59"), pd.to_datetime("2023-01-01T00:30:00")),
        (pd.to_datetime("2023-01-01T00:40:00"), pd.to_datetime("2023-01-01T01:00:00")),
    ])
    def test_next_update(self, trace_sim, dt, expected):
        assert trace_sim.next_update(dt) == expected

    def test_zones(self, trace_sim):
        assert trace_sim.zones() == ["a", "b"]

    def test_trace_actual_at_single_zone(self, trace_sim_series):
        assert trace_sim_series.actual_at("2023-01-01T00:00:00") == 1

    @pytest.mark.parametrize("dt, zone, expected", [
        (pd.to_datetime("2023-01-01T00:00:00"), "a", 1),
        (pd.to_datetime("2023-01-01T00:00:10"), "a", 1),
        (pd.to_datetime("2023-01-01T01:00:00"), "a", 3),
        (pd.to_datetime("2023-01-01T10:00:00"), "a", 3),
        (pd.to_datetime("2023-01-01T00:29:59"), "b", 0),
        (pd.to_datetime("2023-01-01T00:30:00"), "b", 3),
    ])
    def test_trace_actual_at(self, trace_sim, dt, zone, expected):
        assert trace_sim.actual_at(dt, zone) == expected

    def test_trace_actual_at_fails_if_zone_not_specified(self, trace_sim):
        with pytest.raises(ValueError):
            trace_sim.actual_at(pd.to_datetime("2023-01-01T00:00:00"))

    def test_trace_actual_at_fails_if_now_too_early(self, trace_sim):
        with pytest.raises(ValueError):
            trace_sim.actual_at(pd.to_datetime("2022-12-30T23:59:59"), "a")

    def test_trace_actual_at_fails_if_zone_does_not_exist(self, trace_sim):
        with pytest.raises(ValueError):
            trace_sim.actual_at(pd.to_datetime("2023-01-01T00:00:00"), "c")


class TestCarbonApi:

    @pytest.fixture
    def ci_api(self) -> CarbonApi:
        index = [
            pd.to_datetime("2023-01-01T00:00:00"),
            pd.to_datetime("2023-01-01T00:30:00"),
            pd.to_datetime("2023-01-01T01:00:00")
        ]
        actual = pd.DataFrame({"a": [1, 2, 3], "b": [0, 3, 0]}, index=index)
        return CarbonApi(actual)

    def test_initialize_fails_if_unit_unsupported(self):
        with pytest.raises(ValueError):
            CarbonApi(pd.DataFrame(), unit="unsupported_unit")

    def test_carbon_intensity_at_with_lb_per_mwh(self):
        data = pd.DataFrame({"a": [1, 2]})
        ci_api = CarbonApi(data, unit="lb_per_MWh")
        assert 0.45 < ci_api.carbon_intensity_at(0) < 0.46
        assert 0.9 < ci_api.carbon_intensity_at(1) < 0.91


class TestGenerator:

    @pytest.fixture
    def generator(self) -> Generator:
        index = [
            pd.to_datetime("2023-01-01T00:00:00"),
            pd.to_datetime("2023-01-01T00:30:00"),
            pd.to_datetime("2023-01-01T01:00:00")
        ]
        data = pd.Series([1, 2, 3], index=index)
        return Generator(data)

    @pytest.mark.parametrize("dt, expected", [
        (pd.to_datetime("2023-01-01T00:00:00"),  1),
        (pd.to_datetime("2023-01-01T00:00:10"),  1),
        (pd.to_datetime("2023-01-01T01:00:00"),  3),
        (pd.to_datetime("2023-01-01T10:00:00"),  3),
        (pd.to_datetime("2023-01-01T00:29:59"),  1),
        (pd.to_datetime("2023-01-01T00:30:00"),  2),
    ])
    def test_power_at(self, generator, dt, expected):
        assert generator.power_at(dt) == expected
