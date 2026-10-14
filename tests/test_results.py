import csv
import json

import pytest
import yaml

import vessim as vs


def environment():
    env = vs.Environment("2026-01-01", step_size=60)
    env.add_microgrid([vs.Actor("load", vs.StaticSignal(-120))], name="load")
    env.add_microgrid(
        [vs.Actor("solar", vs.StaticSignal(60))],
        dispatchables=[vs.SimpleBattery("battery", 1)],
        name="solar",
    )
    return env


def test_compact_summary_clips_last_interval_and_writes_once(tmp_path):
    env = environment()
    path = tmp_path / "summary.json"
    summary = env.add_controller(vs.Summary(path))

    class Inspect(vs.Controller):
        def step(self, now, states):
            assert not path.exists()

    env.add_controller(Inspect())
    result = env.run(90)
    assert result.steps == 2
    assert summary.duration == 90
    assert summary.metrics["load"]["grid_import_wh"] == 3
    assert summary.metrics["load"]["peak_import_w"] == 120
    assert not hasattr(summary, "log")
    assert len(result.states) == 2
    content = json.loads(path.read_text())
    assert content["status"] == "completed"
    assert content["metrics"] == summary.metrics


def test_csv_heterogeneous_microgrids_use_one_schema(tmp_path):
    env = environment()
    logger = env.add_controller(vs.CsvLogger(tmp_path))
    env.run(180)
    assert logger._file is None
    with logger.csv_path.open() as file:
        reader = csv.DictReader(file)
        rows = list(reader)
    assert len(rows) == 6
    assert [r["microgrid"] for r in rows] == ["load", "solar"] * 3
    assert all(None not in row for row in rows)
    assert rows[0]["dispatch_states.battery.soc"] == ""
    assert rows[1]["actor_states.solar.power"] == "60"
    assert (
        yaml.safe_load((tmp_path / "metadata.yaml").read_text())["execution"]["status"]
        == "completed"
    )


def test_csv_flush_and_schema_change_failure(tmp_path):
    env = environment()
    csv_logger = env.add_controller(vs.CsvLogger(tmp_path, flush=True))

    class Changing(vs.Controller):
        def step(self, now, states):
            assert csv_logger.csv_path.read_text()
            env.microgrids["load"].actors[0].state = lambda t: {"new_column": 1}

    # Custom state is changed after first logging tick; actor.sample must honor
    # instance-level overrides as well as class methods.
    env.add_controller(Changing())
    with pytest.raises(ValueError, match="fields not in fieldnames"):
        env.run(120)
    assert csv_logger._file is None
    assert (
        yaml.safe_load((tmp_path / "metadata.yaml").read_text())["execution"]["status"] == "failed"
    )


def test_interrupted_metadata_and_summary(tmp_path):
    env = environment()
    env.add_controller(vs.CsvLogger(tmp_path))
    env.add_controller(vs.Summary(tmp_path / "summary.json"))

    class Interrupt(vs.Controller):
        def step(self, now, states):
            raise KeyboardInterrupt

    env.add_controller(Interrupt())
    with pytest.raises(KeyboardInterrupt):
        env.run(120)
    assert (
        yaml.safe_load((tmp_path / "metadata.yaml").read_text())["execution"]["status"]
        == "interrupted"
    )
    assert json.loads((tmp_path / "summary.json").read_text())["status"] == "interrupted"
