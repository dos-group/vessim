import functools
import json
from http.server import HTTPServer
from threading import Thread
from urllib.request import urlopen

import numpy as np
import pytest

import vessim as vs
from vessim._cli import _ViewerHandler
from vessim._viewer import Catalog


def record(directory, **kwargs):
    env = vs.Environment("2026-01-01")
    env.add_microgrid(
        [vs.Actor("load", vs.StaticSignal(-100))], name="site", dispatchables=[vs.GridConnection()]
    )
    recorder = env.add_controller(vs.Recorder(directory, **kwargs))
    env.run(1)
    return recorder.result


def test_cli_discovers_and_serves_full_and_compact_records(tmp_path):
    record(tmp_path / "full")
    record(tmp_path / "compact", timeseries=False)
    handler = functools.partial(_ViewerHandler, viewer_dir=tmp_path, catalog=Catalog(tmp_path))
    server = HTTPServer(("127.0.0.1", 0), handler)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with urlopen(base + "/catalog.json", timeout=5) as response:
            listing = json.load(response)
        assert listing["errors"] == []
        compact, full = listing["runs"]
        assert compact["record"]["execution"]["status"] == "completed"
        assert compact["trajectory"] is None
        assert compact["record"]["metrics"]["microgrids"]["site"]["grid_import"] > 0
        with urlopen(base + "/" + full["trajectory"]["url"], timeout=5) as response:
            assert "actor_states.load.power" in response.read().decode()
    finally:
        server.shutdown()
        worker.join()
        server.server_close()


def test_experiment_dict_is_json_compatible_and_detached(tmp_path):
    result = record(tmp_path, timeseries=False, parameters={"seed": np.int64(42)})
    data = result.to_dict()
    assert json.loads(json.dumps(data))["parameters"]["seed"] == 42
    data["parameters"]["seed"] = 99
    assert result.parameters["seed"] == 42
    assert isinstance(data["execution"]["last_time"], str)


@pytest.mark.parametrize(
    "change",
    [
        lambda r: r["metrics"]["microgrids"]["site"].update(grid_import=float("nan")),
        lambda r: r["metrics"]["microgrids"]["site"].update(grid_import=float("inf")),
        lambda r: r["metrics"]["microgrids"]["site"].update(grid_import=True),
        lambda r: r["metric_definitions"]["microgrids"]["site"].pop("grid_import"),
        lambda r: r["metric_definitions"]["microgrids"]["site"]["grid_import"].update(unit=""),
        lambda r: r.update(timeseries=[]),
        lambda r: r.update(timeseries="/absolute.csv"),
        lambda r: r.update(timeseries=12),
        lambda r: r.update(run_id=""),
        lambda r: r.update(schema_version=True),
        lambda r: r["execution"].update(status="unknown"),
        lambda r: r["execution"].update(steps=1.5),
    ],
)
def test_python_loader_and_catalog_reject_the_same_invalid_records(tmp_path, change):
    data = record(tmp_path, timeseries=False).to_dict()
    change(data)
    (tmp_path / "experiment.json").write_text(json.dumps(data))
    with pytest.raises(ValueError):
        vs.ExperimentResult.load(tmp_path)
    catalog = Catalog(tmp_path)
    assert not catalog.runs
    assert len(catalog.errors) == 1


def test_numeric_overflow_in_metadata_is_rejected_by_both_readers(tmp_path):
    record(tmp_path, timeseries=False)
    path = tmp_path / "experiment.json"
    path.write_text(path.read_text().replace('"parameters": {}', '"parameters": {"x": 1e999}'))
    with pytest.raises(ValueError):
        vs.ExperimentResult.load(path)
    assert Catalog(path).errors


def test_save_relocates_csv_and_preserves_source_result(tmp_path, monkeypatch):
    source = tmp_path / "source"
    record(source)
    result = vs.ExperimentResult.load(source)
    original_csv = (source / "timeseries.csv").read_bytes()
    monkeypatch.chdir(tmp_path)
    assert result.timeseries_path == source / "timeseries.csv"
    destination = tmp_path / "export" / "copied.json"
    result.save(destination)
    copied = vs.ExperimentResult.load(destination)
    assert copied.timeseries_path.parent == destination.parent
    assert copied.timeseries_path.read_bytes() == original_csv
    assert result.timeseries_path == source / "timeseries.csv"
    assert result.timeseries == "timeseries.csv"
    assert Catalog(destination).trajectory("0")[0] == original_csv
    # Updating a summary in place neither copies nor truncates its trajectory.
    copied.add_metric("cost", 42, "EUR")
    copied.save(destination)
    assert copied.timeseries_path.read_bytes() == original_csv
    assert vs.ExperimentResult.load(destination).metrics["run"]["cost"] == 42


def test_missing_csv_does_not_replace_destination_summary(tmp_path):
    result = record(tmp_path / "source")
    result.timeseries_path.unlink()
    destination = tmp_path / "export" / "record.json"
    destination.parent.mkdir()
    destination.write_text("previous summary")
    with pytest.raises(FileNotFoundError):
        result.save(destination)
    assert destination.read_text() == "previous summary"


def test_save_cannot_overwrite_its_own_trajectory(tmp_path):
    result = record(tmp_path)
    original = result.timeseries_path.read_bytes()
    with pytest.raises(ValueError, match="must not overwrite"):
        result.save(result.timeseries_path)
    assert result.timeseries_path.read_bytes() == original
