"""Validate site-scoped and coincident metrics in the multi-microgrid example."""

import importlib
from pathlib import Path

import pandas as pd
import pytest


def test_three_microgrids_keep_scope_and_compute_coincident_peak(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "examples"))
    scenario = importlib.import_module("microgrid_comparison")
    result = scenario.run_scenario(tmp_path, "multiple", 1500, 3000, days=1)
    grids = result.metrics["microgrids"]
    assert set(grids) == {"Microgrid 1", "Microgrid 2", "Microgrid 3"}
    assert result.metrics["run"]["total_grid_emissions"] == pytest.approx(
        sum(grid["grid_emissions"] for grid in grids.values())
    )
    frame = pd.read_csv(tmp_path / "multiple/timeseries.csv")
    assert frame.groupby("microgrid").size().tolist() == [24, 24, 24]
    frame["import_power"] = (-frame.p_grid).clip(lower=0)
    peak = frame.groupby("time").import_power.sum().max()
    assert result.metrics["run"]["coincident_import_peak"] == pytest.approx(peak)
    assert peak <= frame.groupby("microgrid").import_power.max().sum()
    assert len(set(grid["energy_consumed"] for grid in grids.values())) == 3
    with pytest.raises(FileExistsError):
        scenario.run_scenario(tmp_path, "multiple", 1500, 3000, days=1)
