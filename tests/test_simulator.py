import pandas as pd
import pytest

from vessim.core.simulator import CarbonApi, Generator


class TestCarbonApi:

    @pytest.fixture
    def ci_api(self) -> CarbonApi:
        index = [
            pd.to_datetime("2023-01-01T00:00:00"),
            pd.to_datetime("2023-01-01T00:30:00"),
            pd.to_datetime("2023-01-01T01:00:00")
        ]
        data = pd.DataFrame({"a": [1, 2, 3], "b": [0, 3, 0]}, index=index)
        return CarbonApi(data)

    def test_initialize_with_unsupported_unit(self):
        with pytest.raises(ValueError):
            CarbonApi(pd.DataFrame(), unit="unsupported_unit")

    @pytest.mark.parametrize("dt, expected", [
        (pd.to_datetime("2023-01-01T00:00:00"), pd.to_datetime("2023-01-01T00:30:00")),
        (pd.to_datetime("2023-01-01T00:10:00"), pd.to_datetime("2023-01-01T00:30:00")),
        (pd.to_datetime("2023-01-01T00:29:59"), pd.to_datetime("2023-01-01T00:30:00")),
        (pd.to_datetime("2023-01-01T00:40:00"), pd.to_datetime("2023-01-01T01:00:00")),
    ])
    def test_next_update(self, ci_api, dt, expected):
        assert ci_api.next_update(dt) == expected

    def test_zones(self, ci_api):
        assert ci_api.zones() == ["a", "b"]

    def test_carbon_intensity_at_single_zone(self):
        ci_api = CarbonApi(pd.DataFrame({"a": [1]}))
        assert ci_api.carbon_intensity_at(0) == 1

    @pytest.mark.parametrize("dt, zone, expected", [
        (pd.to_datetime("2023-01-01T00:00:00"), "a", 1),
        (pd.to_datetime("2023-01-01T00:00:10"), "a", 1),
        (pd.to_datetime("2023-01-01T01:00:00"), "a", 3),
        (pd.to_datetime("2023-01-01T10:00:00"), "a", 3),
        (pd.to_datetime("2023-01-01T00:29:59"), "b", 0),
        (pd.to_datetime("2023-01-01T00:30:00"), "b", 3),
    ])
    def test_carbon_intensity_at(self, ci_api, dt, zone, expected):
        assert ci_api.carbon_intensity_at(dt, zone) == expected

    def test_carbon_intensity_at_fails_if_zone_not_specified(self, ci_api):
        with pytest.raises(ValueError):
            ci_api.carbon_intensity_at(pd.to_datetime("2023-01-01T00:00:00"))

    def test_carbon_intensity_at_fails_if_now_too_early(self, ci_api):
        with pytest.raises(ValueError):
            ci_api.carbon_intensity_at(pd.to_datetime("2022-12-30T23:59:59"), "a")

    def test_carbon_intensity_at_fails_if_zone_does_not_exist(self, ci_api):
        with pytest.raises(ValueError):
            ci_api.carbon_intensity_at(pd.to_datetime("2023-01-01T00:00:00"), "c")

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
    def test_carbon_intensity_at(self, generator, dt, expected):
        assert generator.power_at(dt) == expected

    def test_power_at_fails_if_now_too_early(self, generator):
        with pytest.raises(ValueError):
            generator.power_at(pd.to_datetime("2022-12-30T23:59:59"))
