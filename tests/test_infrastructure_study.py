"""Check the example's accounting and reproducible evaluation contract."""

import importlib
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from vessim import ExperimentResult

SCRIPT = Path(__file__).resolve().parents[1] / "examples/infrastructure_study.py"


@pytest.fixture(scope="module")
def scenario():
    with pytest.MonkeyPatch.context() as patch:
        patch.syspath_prepend(str(SCRIPT.parent))
        yield importlib.import_module("infrastructure_study")


def test_annual_inputs_and_shared_realization(scenario):
    annual = scenario.inputs()
    assert len(annual) == 8760
    assert annual.index[-1] == 365 * 86400 - 3600
    assert np.isfinite(annual).all().all()
    assert annual.solar_cf.between(0, 1).all()
    assert annual.wind_cf.between(0, 1).all()
    assert (annual.load_kw > 0).all()
    pd.testing.assert_frame_equal(annual, scenario.inputs())
    fine = scenario.inputs(step_seconds=900)
    pd.testing.assert_frame_equal(fine.loc[annual.index], annual)
    assert not scenario.inputs(seed=43).equals(annual)
    with pytest.raises(ValueError, match="divide 3600"):
        scenario.inputs(step_seconds=2500)


def test_grid_baseline_matches_input_integrals_and_preserves_output(tmp_path, scenario):
    result = scenario.run_scenario(tmp_path, "baseline", 0, 0, 0, days=2, timeseries=False)
    frame = scenario.inputs(days=2)
    metrics = result.metrics["microgrids"]["Microgrid 1"]
    assert metrics["grid_import"] == pytest.approx(frame.load_kw.sum() * 1000)
    assert metrics["grid_emissions"] == pytest.approx((frame.load_kw * frame.carbon).sum())
    assert metrics["grid_export"] == 0
    assert result.execution["simulated_duration"] == 2 * 86400
    assert result.timeseries is None
    assert scenario.objective_values(result)[0] == 0
    saved = tmp_path / "baseline/experiment.json"
    assert scenario.objective_values(ExperimentResult.load(saved)) == scenario.objective_values(
        result
    )
    with pytest.raises(FileExistsError, match="Preserving"):
        scenario.run_scenario(tmp_path, "baseline", 0, 0, 0, days=2, timeseries=False)
    result.metrics["microgrids"]["Microgrid 1"]["grid_emissions"] = None
    with pytest.raises(ValueError, match="finite"):
        scenario.objective_values(result)
    result.execution["status"] = "failed"
    with pytest.raises(ValueError, match="complete"):
        scenario.objective_values(result)


def test_storage_energy_balance_and_recorded_emissions(tmp_path, scenario):
    result = scenario.run_scenario(tmp_path, "storage", 1500, 4000, 8000, days=3, timeseries=True)
    frame = pd.read_csv(tmp_path / "storage/timeseries.csv")
    imports = (-frame.p_grid).clip(lower=0)
    expected_emissions = (imports.to_numpy() / 1000 * scenario.inputs(days=3).carbon).sum()
    assert scenario.objective_values(result) == pytest.approx((3800000, expected_emissions))
    metrics = result.metrics["microgrids"]["Microgrid 1"]
    # Empty initial storage, no battery losses: net input equals final stored energy.
    stored = (
        metrics["energy_produced"]
        + metrics["grid_import"]
        - metrics["energy_consumed"]
        - metrics["grid_export"]
    )
    charge = frame["dispatch_states.battery.charge_level"]
    battery_power = frame.p_delta - frame.p_grid
    # Recorded state is at the beginning of each held dispatch interval.
    np.testing.assert_allclose(np.diff(charge), battery_power.iloc[:-1], atol=1e-5)
    terminal_charge = charge.iloc[-1] + battery_power.iloc[-1]  # one-hour final interval
    assert stored == pytest.approx(terminal_charge, abs=1e-5)
    assert len(frame) == 72


def test_optuna_records_objectives_and_preserves_existing_output(tmp_path, scenario):
    optuna = pytest.importorskip("optuna")
    command = [
        sys.executable,
        str(SCRIPT),
        "--output",
        str(tmp_path),
        "--days",
        "1",
        "--trials",
        "2",
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    storage = optuna.storages.RDBStorage(f"sqlite:///{tmp_path / 'optuna.db'}")
    try:
        study = optuna.load_study(study_name="infrastructure-emissions", storage=storage)
        completed = study.get_trials(states=(optuna.trial.TrialState.COMPLETE,))
    finally:
        storage.remove_session()
        storage.engine.dispose()
    assert len(completed) == 2
    for trial in completed:
        record = ExperimentResult.load(tmp_path / trial.user_attrs["vessim_experiment"])
        assert trial.user_attrs["vessim_run_id"] == record.run_id
        assert trial.values == list(scenario.objective_values(record))
    before = (tmp_path / "study.json").read_bytes()
    command[command.index("--days") + 1] = "2"
    rejected = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert rejected.returncode != 0
    assert "Output is not empty" in rejected.stderr
    assert (tmp_path / "study.json").read_bytes() == before


def test_financial_metrics_match_recorded_cashflows_and_annual_allocation(tmp_path, scenario):
    result = scenario.run_scenario(
        tmp_path,
        "financial",
        1500,
        2000,
        4000,
        financial=True,
        battery_c_rate=0.25,
        timeseries=True,
    )
    frame = pd.read_csv(tmp_path / "financial/timeseries.csv")
    grid = result.metrics["microgrids"]["Microgrid 1"]
    imports = (-frame.p_grid).clip(lower=0) / 1000
    exports = frame.p_grid.clip(lower=0) / 1000
    assert grid["electricity_cost"] == pytest.approx((imports * frame["grid_signals.price"]).sum())
    assert grid["export_revenue"] == pytest.approx(
        (exports * frame["grid_signals.export_price"]).sum()
    )
    capital = 1500 * 1300 + 2000 * 700 + 4000 * 300
    annual = 1500 * 1300 / 20 + 2000 * 700 / 25 + 4000 * 300 / 10
    assert result.metrics["run"]["equipment_capex"] == capital
    assert result.metrics["run"]["annualized_equipment_cost"] == annual
    assert scenario.objective_values(result, financial=True)[0] == pytest.approx(
        annual + grid["electricity_cost"] - grid["export_revenue"]
    )
    assert result.parameters["battery_c_rate"] == 0.25
    assert len(frame) == 8760
    with pytest.raises(ValueError, match="365-day"):
        scenario.run_scenario(tmp_path, "short-finance", 0, 0, 0, financial=True, days=1)
