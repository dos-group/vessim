"""Viewer input origins, partial catalogs, lazy artifacts, and static export."""

import json
from pathlib import Path

import pytest

from vessim._viewer import Catalog


def record(trajectory=None, run_id="same-id"):
    return {
        "format": "vessim.experiment",
        "schema_version": 1,
        "run_id": run_id,
        "config": {"microgrids": {}},
        "parameters": {"seed": 42},
        "execution": {"status": "interrupted"},
        "metrics": {"run": {"missing": None}, "microgrids": {}, "actors": {}},
        "metric_definitions": {"run": {"missing": {"unit": "1"}}, "microgrids": {}, "actors": {}},
        "timeseries": trajectory,
    }


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return path


def test_file_directory_and_collection_preserve_records(tmp_path):
    file = save(tmp_path / "a" / "experiment.json", record())
    save(tmp_path / "b" / "experiment.json", record())
    for path in (file, file.parent, tmp_path):
        catalog = Catalog(path)
        assert not catalog.errors
        assert len(catalog.runs) == (2 if path == tmp_path else 1)
        assert catalog.runs[0]["record"]["metrics"]["run"]["missing"] is None
        assert catalog.runs[0]["record"]["execution"]["status"] == "interrupted"
    assert len({run["key"] for run in Catalog(tmp_path).runs}) == 2


def test_csv_study_trajectories_are_lazy_and_relative(tmp_path, monkeypatch):
    file = save(
        tmp_path / "study.json",
        {
            "format": "vessim.study",
            "schema_version": 1,
            "experiments": [record("nested/power.csv")],
        },
    )
    (tmp_path / "nested").mkdir()
    csv = tmp_path / "nested" / "power.csv"
    csv.write_text("microgrid,time,p_grid\nsite,2026-01-01,-1\n")
    original = Path.read_bytes
    monkeypatch.setattr(Path, "read_bytes", lambda path: pytest.fail("Trajectory read eagerly"))
    catalog = Catalog(file)
    payload = catalog.payload()
    assert all("timeseries" not in run["record"] for run in payload["runs"])
    assert all("microgrids" not in run["trajectory"] for run in payload["runs"])
    monkeypatch.setattr(Path, "read_bytes", original)
    assert catalog.trajectory("0")[0] == csv.read_bytes()


def test_partial_catalog_unknown_versions_and_missing_csv(tmp_path):
    save(tmp_path / "a" / "experiment.json", record("missing.csv"))
    save(tmp_path / "b" / "experiment.json", {**record(), "schema_version": 99})
    save(tmp_path / "c" / "experiment.json", record())
    catalog = Catalog(tmp_path)
    assert len(catalog.runs) == 2
    assert len(catalog.errors) == 1
    with pytest.raises(FileNotFoundError):
        catalog.trajectory("0")


@pytest.mark.parametrize("reference", ["../outside.csv", "/etc/passwd"])
def test_trajectory_cannot_escape_results_root(tmp_path, reference):
    file = save(tmp_path / "experiment.json", record(reference))
    catalog = Catalog(file)
    assert not catalog.runs
    assert "within" in catalog.errors[0] or "relative CSV" in catalog.errors[0]


def test_static_export_uses_same_manifest_and_lazy_urls(tmp_path):
    file = save(tmp_path / "source" / "experiment.json", record("timeseries.csv"))
    (file.parent / "timeseries.csv").write_text("microgrid,time,p_grid\nsite,2026-01-01,-1\n")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "index.html").write_text("viewer")
    catalog = Catalog(file)
    destination = tmp_path / "export"
    catalog.export(destination, assets)
    payload = json.loads((destination / "catalog.json").read_text())
    assert payload == catalog.payload()
    assert (destination / payload["runs"][0]["trajectory"]["url"]).read_bytes() == (
        file.parent / "timeseries.csv"
    ).read_bytes()
    with pytest.raises(ValueError, match="empty"):
        catalog.export(destination, assets)


def test_nonfinite_json_is_reported_instead_of_breaking_catalog_response(tmp_path):
    data = record()
    data["metrics"]["run"]["bad"] = float("nan")
    file = save(tmp_path / "experiment.json", data)
    catalog = Catalog(file)
    assert not catalog.runs
    assert "Nonfinite" in catalog.errors[0]
