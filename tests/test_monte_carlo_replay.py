"""Check native Monte Carlo accounting, reproducibility and process execution."""

import importlib
import json
from pathlib import Path

import pandas as pd
import pytest

from vessim._experiment import validate_record


@pytest.fixture
def scenario(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / "examples"))
    return importlib.import_module("monte_carlo_replay")


def test_sampled_years_are_reproducible_and_have_persistent_variation(scenario):
    first, factors = scenario.sampled_inputs(10000, days=3)
    repeated, again = scenario.sampled_inputs(10000, days=3)
    pd.testing.assert_frame_equal(first, repeated)
    assert factors == again
    second, other = scenario.sampled_inputs(10001, days=3)
    assert factors != other
    assert not first.equals(second)
    for key, value in factors.items():
        low, _, high = scenario.FACTORS[key]
        assert low <= value <= high
    assert first.solar_cf.between(0, 1).all()
    assert first.wind_cf.between(0, 1).all()
    assert (first.load_kw > 0).all()
    assert first.export_price.iloc[0] == pytest.approx(0.04 * factors["price_multiplier"])


CONFIGS = [
    dict(wind_kw=0, solar_kw=0, battery_kwh=0, battery_c_rate=0.5),
    dict(wind_kw=1500, solar_kw=2000, battery_kwh=4000, battery_c_rate=0.25),
]


def source_study(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    groups = []
    for i, config in enumerate(CONFIGS):
        path = source / f"trial-{i}.json"
        path.write_text(json.dumps({"parameters": config}))
        groups.append({"configuration_id": f"trial-{i}", "runs": [{"path": path.name}]})
    index = source / "study.json"
    index.write_text(json.dumps({"configurations": groups}))
    return index


def expand(path):
    batch = json.loads(path.read_text())
    shared = batch["shared"]
    records = [
        {**shared, **record, "parameters": {**shared["parameters"], **record["parameters"]}}
        for record in batch["runs"]
    ]
    for record in records:
        validate_record(record)
    return records


@pytest.mark.parametrize("days", [3, 365])
def test_native_grid_only_accounting(scenario, days):
    record = scenario.run_scenario("grid", CONFIGS[0], 10000, days=days)
    frame, _ = scenario.sampled_inputs(10000, days=days)
    grid = record["metrics"]["microgrids"]["Microgrid 1"]
    assert grid["grid_import"] == pytest.approx(frame.load_kw.sum() * 1000)
    assert grid["grid_emissions"] == pytest.approx((frame.load_kw * frame.carbon).sum())
    assert grid["electricity_cost"] == pytest.approx((frame.load_kw * frame.price).sum())
    assert grid["grid_export"] == grid["export_revenue"] == grid["final_battery_energy"] == 0
    assert record["config"]["environment"]["backend"] == "native"
    assert record["execution"]["steps"] == days * 24
    assert record["execution"]["wall_time"] > 0


def test_parallel_replay_matches_serial_and_preserves_runs(scenario, tmp_path):
    source = source_study(tmp_path)
    serial = scenario.build(source, tmp_path / "serial", runs=3, chunk_size=2)
    parallel = scenario.build(source, tmp_path / "parallel", runs=3, chunk_size=1, workers=2)
    assert serial["configurations"] == parallel["configurations"]
    assert parallel["runtime"]["evaluations"] == 6
    assert parallel["runtime"]["workers"] == 2
    assert parallel["runtime"]["evaluator"] == "native"
    assert parallel["runtime"]["simulation_wall_seconds_sum"] > 0
    all_records = []
    for i in range(2):
        before = expand(tmp_path / f"serial/trial-{i}.json")
        after = expand(tmp_path / f"parallel/trial-{i}.json")
        assert [r["run_id"] for r in after] == [
            f"trial-{i}-s{seed}" for seed in range(10000, 10003)
        ]
        for first, second in zip(before, after):
            assert first["parameters"] == second["parameters"]
            assert first["metrics"] == second["metrics"]
            assert second["execution"]["status"] == "completed"
            assert second["execution"]["steps"] == 8760
            assert second["execution"]["wall_time"] > 0
            grid = second["metrics"]["microgrids"]["Microgrid 1"]
            assert grid["final_battery_energy"] == pytest.approx(
                grid["energy_produced"]
                + grid["grid_import"]
                - grid["energy_consumed"]
                - grid["grid_export"],
                abs=1e-4,
            )
            metrics = second["metrics"]["run"]
            assert metrics["annual_cost"] == pytest.approx(
                metrics["annualized_equipment_cost"]
                + grid["electricity_cost"]
                - grid["export_revenue"]
            )
        all_records.append(after)
    for first, second in zip(*all_records):
        assert {k: first["parameters"][k] for k in scenario.FACTORS} == {
            k: second["parameters"][k] for k in scenario.FACTORS
        }
    saved = (tmp_path / "serial/study.json").read_bytes()
    with pytest.raises(FileExistsError):
        scenario.build(source, tmp_path / "serial", runs=1)
    assert (tmp_path / "serial/study.json").read_bytes() == saved
    assert not list(tmp_path.glob("parallel/*.partial"))


def test_failure_does_not_publish_a_completed_study(scenario, tmp_path, monkeypatch):
    source = source_study(tmp_path)
    original = scenario.run_scenario

    def fail(identity, parameters, seed):
        if seed == 10001:
            raise ValueError("failed scenario")
        return original(identity, parameters, seed)

    monkeypatch.setattr(scenario, "run_scenario", fail)
    output = tmp_path / "failed"
    with pytest.raises(RuntimeError, match="trial-0-s10001"):
        scenario.build(source, output, runs=2, chunk_size=1)
    assert not (output / "study.json").exists()
    assert (output / "trial-0.json.partial").exists()


def test_worker_failure_is_propagated(scenario):
    invalid = {**CONFIGS[0], "battery_kwh": -1}
    tasks = [("broken", invalid, [10000])]
    with pytest.raises(RuntimeError, match="broken-s10000"):
        list(scenario.evaluate_tasks(tasks, workers=2))


@pytest.mark.parametrize(
    "options", [{"workers": 0}, {"chunk_size": 0}, {"runs": 0}, {"seed_start": -1}]
)
def test_invalid_settings_fail_before_creating_output(scenario, tmp_path, options):
    source = source_study(tmp_path)
    output = tmp_path / "invalid"
    with pytest.raises(ValueError):
        scenario.build(source, output, **{"runs": 1, **options})
    assert not output.exists()


def test_unsafe_configuration_ids_are_rejected(scenario, tmp_path):
    source = source_study(tmp_path)
    document = json.loads(source.read_text())
    document["configurations"][0]["configuration_id"] = "../outside"
    source.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="safe filenames"):
        scenario.build(source, tmp_path / "output", runs=1)


def test_configuration_selection_is_exact_and_rejects_unknown_ids(scenario, tmp_path):
    source = source_study(tmp_path)
    assert scenario.load_configurations(source, ["trial-1"]) == [("trial-1", CONFIGS[1])]
    assert [
        identity for identity, _ in scenario.load_configurations(source, ["trial-1", "trial-0"])
    ] == ["trial-1", "trial-0"]
    for identities in (["missing"], [], ["trial-0", "trial-0"]):
        with pytest.raises(ValueError):
            scenario.build(source, tmp_path / "invalid", runs=1, configuration_ids=identities)
    assert not (tmp_path / "invalid").exists()
