"""Canonical study loading, missing records, lazy artifacts and portable exports."""

import json
from pathlib import Path

import pytest

from vessim._viewer import Catalog


def record(trajectory=None, run_id="run", status="completed"):
    return {
        "format": "vessim.experiment",
        "schema_version": 1,
        "run_id": run_id,
        "config": {"microgrids": {}},
        "parameters": {"seed": 42},
        "execution": {"status": status},
        "metrics": {"run": {"missing": None}, "microgrids": {}, "actors": {}},
        "metric_definitions": {"run": {"missing": {"unit": "1"}}, "microgrids": {}, "actors": {}},
        "timeseries": trajectory,
    }


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return path


def study(configurations, identity="study"):
    return {
        "format": "vessim.study",
        "schema_version": 2,
        "study_id": identity,
        "name": identity,
        "run_parameters": ["seed"],
        "configurations": configurations,
    }


def test_file_directory_collection_and_summary_only(tmp_path):
    file = save(tmp_path / "a/experiment.json", record(run_id="a"))
    save(tmp_path / "b/experiment.json", record(run_id="b"))
    for path in (file, file.parent, tmp_path):
        catalog = Catalog(path)
        assert not catalog.errors
        assert len(catalog.runs) == (2 if path == tmp_path else 1)
        assert catalog.runs[0]["record"]["metrics"]["run"]["missing"] is None
        assert catalog.runs[0]["trajectoryUrl"] is None
        assert "configurations" not in catalog.payload()["studies"][0]


def test_study_preserves_grouping_and_relative_origins_without_reading_csv(tmp_path, monkeypatch):
    save(tmp_path / "records/a/experiment.json", record("power.csv", "a"))
    save(tmp_path / "records/b/experiment.json", record(run_id="b"))
    csv = tmp_path / "records/a/power.csv"
    csv.write_text("microgrid,time,p_grid\nsite,2026-01-01,-1\n")
    index = save(
        tmp_path / "indexes/study.json",
        study(
            [
                {
                    "configuration_id": "candidate",
                    "name": "Candidate",
                    "runs": [
                        {"path": "../records/a/experiment.json"},
                        {"path": "../records/b/experiment.json"},
                    ],
                }
            ]
        ),
    )
    original = Path.read_bytes
    monkeypatch.setattr(Path, "read_bytes", lambda _: pytest.fail("Trajectory read eagerly"))
    catalog = Catalog(index)
    group = catalog.study("0")["configurations"][0]
    assert group["name"] == "Candidate"
    assert [r["run_id"] for r in group["runs"]] == ["a", "b"]
    assert not catalog.errors
    assert catalog.study("0")["run_parameters"] == ["seed"]
    monkeypatch.setattr(Path, "read_bytes", original)
    assert catalog.trajectory("0")[0] == csv.read_bytes()


def test_partial_catalog_excludes_incomplete_and_invalid_records(tmp_path):
    save(tmp_path / "a/experiment.json", record("missing.csv", "a"))
    save(tmp_path / "b/experiment.json", {**record(), "schema_version": 99})
    save(tmp_path / "c/experiment.json", record(run_id="c", status="interrupted"))
    save(tmp_path / "d/experiment.json", record(run_id="d", status="failed"))
    catalog = Catalog(tmp_path)
    assert len(catalog.runs) == 1
    assert len(catalog.errors) == 3
    with pytest.raises(FileNotFoundError):
        catalog.trajectory("0")


@pytest.mark.parametrize("reference", ["../outside.csv", "/etc/passwd"])
def test_trajectory_cannot_escape_experiment_directory(tmp_path, reference):
    catalog = Catalog(save(tmp_path / "experiment.json", record(reference)))
    assert not catalog.runs
    assert "within" in catalog.errors[0] or "relative CSV" in catalog.errors[0]


def test_static_export_uses_same_summaries_and_lazy_urls(tmp_path):
    file = save(tmp_path / "source/experiment.json", record("timeseries.csv"))
    (file.parent / "timeseries.csv").write_text("microgrid,time,p_grid\nsite,2026-01-01,-1\n")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "index.html").write_text("viewer")
    catalog = Catalog(file)
    destination = tmp_path / "export"
    catalog.export(destination, assets)
    payload = json.loads((destination / "catalog.json").read_text())
    assert payload == catalog.payload()
    exported = json.loads((destination / payload["studies"][0]["url"]).read_text())
    assert exported == catalog.study("0")
    assert (
        destination / exported["configurations"][0]["runs"][0]["trajectoryUrl"]
    ).read_bytes() == (file.parent / "timeseries.csv").read_bytes()
    with pytest.raises(ValueError, match="empty"):
        catalog.export(destination, assets)


def test_duplicates_missing_references_and_unsupported_study_version(tmp_path):
    save(tmp_path / "a/experiment.json", record(run_id="a"))
    file = save(
        tmp_path / "study.json",
        study(
            [
                {
                    "configuration_id": "c",
                    "runs": [
                        {"path": "a/experiment.json"},
                        {"path": "a/experiment.json"},
                        {"path": "missing/experiment.json"},
                    ],
                }
            ]
        ),
    )
    catalog = Catalog(file)
    assert len(catalog.runs) == 1
    assert len(catalog.errors) == 2
    assert "Duplicate run_id" in catalog.errors[0]
    save(file, {**study([]), "schema_version": 1})
    assert "schema_version 2" in Catalog(file).errors[0]


def test_batch_and_multiple_studies(tmp_path):
    shared = record()
    save(
        tmp_path / "first/batch.json",
        {
            "format": "vessim.viewer.run-batch",
            "schema_version": 1,
            "shared": shared,
            "runs": [
                {"run_id": "seed-1", "parameters": {"seed": 1}},
                {"run_id": "seed-2", "parameters": {"seed": 2}},
            ],
        },
    )
    save(
        tmp_path / "first/study.json",
        study([{"configuration_id": "c", "run_batch": "batch.json"}], "first"),
    )
    save(tmp_path / "second/study.json", study([], "second"))
    catalog = Catalog(tmp_path)
    assert not catalog.errors
    assert len(catalog.payload()["studies"]) == 2
    assert [r["record"]["parameters"]["seed"] for r in catalog.runs] == [1, 2]
    assert catalog.runs[0]["record"]["metrics"] == shared["metrics"]


def test_nonfinite_json_is_reported(tmp_path):
    data = record()
    data["metrics"]["run"]["bad"] = float("nan")
    catalog = Catalog(save(tmp_path / "experiment.json", data))
    assert not catalog.runs
    assert "Nonfinite" in catalog.errors[0]
