"""Check that the documentation gallery can be hosted independently of the checkout."""

import importlib.util
import json
from pathlib import Path
import shutil

import pytest
import vessim as vs

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("export_docs", ROOT / "viewer/export_docs.py")
export_docs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(export_docs)


@pytest.fixture
def gallery(tmp_path, monkeypatch):
    root = tmp_path / "checkout"
    assets = root / "vessim/_viewer_dist"
    shutil.copytree(ROOT / "vessim/_viewer_dist", assets)
    run = root / "results/recordings/run"
    with vs.Environment("2026-01-01", step_size=60) as env:
        env.add_microgrid(
            name="site",
            actors=[vs.Consumer("load", 700)],
            dispatchables=[vs.GridConnection()],
        )
        env.add_controller(vs.Recorder(run))
        env.run(120)
    record = vs.ExperimentResult.load(run)
    record.config["input_file"] = str(root / "datasets/input.csv")
    record.save(run / "experiment.json")
    index = root / "results/viewer-proposal/example/study.json"
    index.parent.mkdir(parents=True)
    index.write_text(
        json.dumps(
            {
                "format": "vessim.study",
                "schema_version": 2,
                "study_id": "example",
                "configurations": [
                    {
                        "configuration_id": "one",
                        "runs": [
                            {"path": "../../recordings/run/experiment.json"},
                        ],
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(export_docs, "STUDIES", ("example",))
    return root, run


def test_export_relocates_recordings_and_preserves_sources(gallery, tmp_path):
    root, source = gallery
    before = {file.name: file.read_bytes() for file in source.iterdir()}
    destination = tmp_path / "published/en/latest/viewer"
    export_docs.export_gallery(destination, root)
    catalog = json.loads((destination / "catalog.json").read_text())
    study = json.loads((destination / catalog["studies"][0]["url"]).read_text())
    run = study["configurations"][0]["runs"][0]
    assert (destination / run["trajectoryUrl"]).read_bytes() == before["timeseries.csv"]
    assert run["record"]["metrics"]["microgrids"]["site"]["grid_import"] == pytest.approx(700 / 30)
    assert run["record"]["config"]["input_file"] == "datasets/input.csv"
    assert {file.name: file.read_bytes() for file in source.iterdir()} == before
    assert "node_modules" not in (destination / "index.html").read_text()
    assert 'id="proposal"' not in (destination / "index.html").read_text()
    assert (destination / "vendor/echarts.min.js").is_file()
    assert (destination / "vendor/papaparse.min.js").is_file()


def test_failed_export_preserves_existing_gallery(gallery, tmp_path):
    root, source = gallery
    record = vs.ExperimentResult.load(source)
    record.execution["status"] = "failed"
    record.save(source / "experiment.json")
    destination = tmp_path / "existing"
    destination.mkdir()
    (destination / "keep.txt").write_text("previous gallery")
    with pytest.raises(ValueError, match="not complete"):
        export_docs.export_gallery(destination, root)
    assert (destination / "keep.txt").read_text() == "previous gallery"
