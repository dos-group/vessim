import pandas as pd
import pytest

from vessim.carbon_api import CarbonApi


class TestCarbonApi:

    @pytest.fixture
    def ci_api(self) -> CarbonApi:
        index = [pd.to_datetime("2023-01-01T00:00:00"),
                 pd.to_datetime("2023-01-01T00:30:00"),
                 pd.to_datetime("2023-01-01T01:00:00")]
        data = pd.DataFrame({"a": [1, 2, 3], "b": [0, 3, 0]}, index=index)
        return CarbonApi(data)

    def test_zones(self, ci_api):
        assert ci_api.zones() == ["a", "b"]

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

    def test_carbon_intensity_at_fails_if_now_too_early(self, ci_api):
        with pytest.raises(ValueError):
            ci_api.carbon_intensity_at(pd.to_datetime("2022-12-30T23:59:59"), "a")

    def test_carbon_intensity_at_fails_if_zone_does_not_exist(self, ci_api):
        with pytest.raises(ValueError):
            ci_api.carbon_intensity_at(pd.to_datetime("2023-01-01T00:00:00"), "c")
