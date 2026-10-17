import csv
import json
import math

import pandas as pd
import pytest

import vessim as vs


def environment(backend="native"):
    env = vs.Environment("2026-01-01", step_size=60, backend=backend)
    env.add_microgrid(
        [vs.Actor("load", vs.StaticSignal(-120))], name="load", dispatchables=[vs.GridConnection()]
    )
    env.add_microgrid(
        [vs.Actor("solar", vs.StaticSignal(60))],
        dispatchables=[vs.SimpleBattery("battery", 1), vs.GridConnection()],
        name="solar",
    )
    return env


@pytest.mark.parametrize("backend", ["native", "mosaik"])
def test_compact_record_clips_last_interval_and_writes_once(tmp_path, backend):
    if backend == "mosaik":
        pytest.importorskip("mosaik")
    env = environment(backend)
    recorder = env.add_controller(vs.Recorder(tmp_path, timeseries=False))

    class Inspect(vs.Controller):
        def step(self, now, states):
            assert not (tmp_path / "experiment.json").exists()

    env.add_controller(Inspect())
    env.run(90)
    assert recorder.duration == 90
    assert recorder.metrics["microgrids"]["load"]["grid_import"] == 3
    assert recorder.metrics["microgrids"]["load"]["peak_grid_import"] == 120
    assert recorder.metrics["actors"]["load"]["load"]["energy_consumed"] == 3
    assert recorder.log == {}
    assert not recorder.csv_path.exists()
    result = vs.ExperimentResult.load(tmp_path)
    assert result.execution["status"] == "completed"
    assert result.metrics == recorder.metrics
    assert result.timeseries is None
    assert result.metric_definitions["actors"]["load"]["load"]["energy_consumed"]["unit"] == "Wh"


def test_defaults_stream_csv_and_use_one_schema(tmp_path):
    env = environment()
    recorder = env.add_controller(vs.Recorder(tmp_path))
    env.run(180)
    assert recorder._file is None
    assert not recorder.log
    with recorder.csv_path.open() as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 6
    assert [r["microgrid"] for r in rows] == ["load", "solar"] * 3
    assert all(None not in row for row in rows)
    assert rows[0]["dispatch_states.battery.soc"] == ""
    assert rows[1]["actor_states.solar.power"] == "60"
    result = vs.ExperimentResult.load(tmp_path)
    assert result.execution["status"] == "completed"
    assert result.timeseries == "timeseries.csv"
    assert result.metrics["microgrids"]["load"]["energy_consumed"] == 6
    assert len(recorder.to_df()) == 6


def test_csv_flush_and_schema_change_failure(tmp_path):
    env = environment()
    recorder = env.add_controller(vs.Recorder(tmp_path, flush=True))

    class Changing(vs.Controller):
        def step(self, now, states):
            assert recorder.csv_path.read_text()
            assert vs.ExperimentResult.load(tmp_path).execution["status"] == "running"
            env.microgrids["load"].actors[0].state = lambda t: {"new_column": 1}

    env.add_controller(Changing())
    with pytest.raises(ValueError, match="fields not in fieldnames"):
        env.run(120)
    assert recorder._file is None
    assert vs.ExperimentResult.load(tmp_path).execution["status"] == "failed"


@pytest.mark.parametrize("failure", [KeyboardInterrupt(), ValueError("broken controller")])
def test_partial_records_preserve_status(tmp_path, failure):
    env = environment()
    recorder = env.add_controller(vs.Recorder(tmp_path))

    class Interrupt(vs.Controller):
        def step(self, now, states):
            raise failure

    env.add_controller(Interrupt())
    with pytest.raises(type(failure)):
        env.run(120)
    result = vs.ExperimentResult.load(tmp_path)
    assert result.execution["status"] == (
        "interrupted" if isinstance(failure, KeyboardInterrupt) else "failed"
    )
    assert result.execution["steps"] == 1
    assert recorder._file is None


def test_production_and_consumption_are_separate_not_net():
    env = vs.Environment("2026-01-01", step_size=60)
    trace = vs.Trace(pd.Series([60, -120, 60], index=[0, 60, 120]))
    env.add_microgrid(
        [
            vs.Actor("bidirectional", trace),
            vs.Actor("load", vs.StaticSignal(60), consumer=True),
        ],
        name="grid",
        dispatchables=[vs.GridConnection()],
    )
    recorder = env.add_controller(vs.Recorder(timeseries=False))
    env.run(150)
    grid = recorder.metrics["microgrids"]["grid"]
    actor = recorder.metrics["actors"]["grid"]["bidirectional"]
    assert actor == {"energy_produced": 1.5, "energy_consumed": 2.0}
    assert grid["energy_produced"] == 1.5
    assert grid["energy_consumed"] == 4.5
    assert grid["grid_import"] == 3
    assert grid["grid_export"] == 0


def test_metrics_use_sampled_power_independent_of_custom_state():
    class DiagnosticActor(vs.Actor):
        def state(self, elapsed):
            return {"temperature": 20, "power": 9999}

    env = vs.Environment("2026-01-01")
    env.add_microgrid(
        [DiagnosticActor("device", vs.StaticSignal(-3600), step_size=2)],
        dispatchables=[vs.GridConnection()],
    )
    recorder = env.add_controller(vs.Recorder(timeseries=False))
    env.run(2.5)
    assert recorder.metrics["actors"]["microgrid_0"]["device"]["energy_consumed"] == 2.5


def test_custom_metrics_static_accumulated_derived_and_scoped(tmp_path):
    class HighImportDuration(vs.Metric):
        def step(self, now, states, duration):
            if states["load"]["p_grid"] < -100:
                self.value += duration

    class Undefined(vs.Metric):
        def finalize(self):
            return None

    env = environment()
    recorder = env.add_controller(
        vs.Recorder(
            tmp_path,
            timeseries=False,
            parameters={"seed": 42},
            run_id="trial-42",
            custom_metrics={
                "high_import_duration": HighImportDuration("s", microgrid="load"),
                "undefined_ratio": Undefined("1"),
            },
        )
    )
    env.run(90)
    recorder.result.add_metric("capex", 1000, "EUR", assumptions={"source": "example"})
    recorder.result.add_metric("area", 5, "m2", microgrid="solar", actor="solar")
    recorder.result.add_metric("double_capex", recorder.metrics["run"]["capex"] * 2, "EUR")
    recorder.result.save(tmp_path / "experiment.json")
    result = vs.ExperimentResult.load(tmp_path)
    assert result.metrics["run"] == {"capex": 1000, "double_capex": 2000, "undefined_ratio": None}
    assert result.metrics["microgrids"]["load"]["high_import_duration"] == 90
    assert result.metrics["actors"]["solar"]["solar"]["area"] == 5
    assert result.parameters == {"seed": 42}
    assert result.run_id == "trial-42"
    assert result.metric_definitions["run"]["capex"]["assumptions"] == {"source": "example"}
    detached = recorder.result.to_dict()
    detached["metrics"]["run"]["capex"] = 999
    assert recorder.metrics["run"]["capex"] == 1000


@pytest.mark.parametrize("backend", ["native", "mosaik"])
def test_optional_price_and_carbon_integrals(backend):
    if backend == "mosaik":
        pytest.importorskip("mosaik")
    env = vs.Environment("2026-01-01", step_size=60, backend=backend)
    env.add_microgrid(
        [vs.Actor("device", vs.Trace(pd.Series([-6000, 6000], index=[0, 60])))],
        name="grid",
        grid_signals={
            "buy": vs.Trace(pd.Series([0.2, 0.5], index=[0, 60])),
            "sell": vs.StaticSignal(-0.1),
            "carbon": vs.StaticSignal(0.4),
        },
        dispatchables=[vs.GridConnection()],
    )
    rec = env.add_controller(
        vs.Recorder(
            timeseries=False,
            custom_metrics={
                "electricity_import_cost": vs.ElectricityImportCost("grid", "buy"),
                "electricity_export_revenue": vs.ElectricityExportRevenue("grid", "sell"),
                "grid_import_emissions": vs.GridImportEmissions("grid", "carbon"),
            },
        )
    )
    env.run(90)
    m = rec.metrics["microgrids"]["grid"]
    assert m["electricity_import_cost"] == pytest.approx(0.02)
    assert m["electricity_export_revenue"] == pytest.approx(-0.005)
    assert m["grid_import_emissions"] == pytest.approx(0.04)


@pytest.mark.parametrize(
    "custom,match",
    [
        ({"cost": vs.ElectricityImportCost("load", "missing")}, "requires grid signal"),
        ({"grid_import": vs.Metric("Wh", microgrid="load")}, "already exists"),
        ({"x": vs.Metric("Wh", microgrid="missing")}, "Unknown scope"),
    ],
)
def test_invalid_custom_configuration_fails_before_stepping(tmp_path, custom, match):
    env = environment()
    rec = env.add_controller(vs.Recorder(tmp_path, custom_metrics=custom))
    with pytest.raises(ValueError, match=match):
        env.run(60)
    assert rec.steps == 0
    assert vs.ExperimentResult.load(tmp_path).execution["status"] == "failed"


def test_finalizer_failure_keeps_other_metric_results_and_valid_json(tmp_path):
    class Bad(vs.Metric):
        def finalize(self):
            return math.nan

    env = environment()
    env.add_controller(
        vs.Recorder(
            tmp_path,
            custom_metrics={
                "bad": Bad("1"),
                "good": vs.Metric("1"),
            },
        )
    )
    with pytest.raises(ValueError, match="finite"):
        env.run(60)
    result = vs.ExperimentResult.load(tmp_path)
    assert result.execution["status"] == "failed"
    assert result.metrics["run"] == {"bad": None, "good": 0}


def test_metrics_can_be_disabled_independently():
    env = environment()
    rec = env.add_controller(
        vs.Recorder(
            metrics=False,
            custom_metrics={
                "custom": vs.Metric("1"),
            },
        )
    )
    env.run(60)
    assert rec.metrics["microgrids"]["load"] == {}
    assert rec.metrics["run"] == {"custom": 0}
    assert len(rec.log) == 1


def test_empty_run_is_valid_and_serializable(tmp_path):
    env = environment()
    rec = env.add_controller(vs.Recorder())
    env.run(0)
    assert rec.to_df().empty
    assert rec.result.timeseries is None
    assert rec.result.execution["last_time"] is None
    assert rec.metrics["microgrids"]["load"]["grid_import"] == 0
    rec.result.save(tmp_path / "empty.json")
    assert vs.ExperimentResult.load(tmp_path / "empty.json").execution["steps"] == 0


def test_reader_rejects_unknown_format(tmp_path):
    path = tmp_path / "experiment.json"
    path.write_text(json.dumps({"format": "vessim.experiment", "schema_version": 99}))
    with pytest.raises(ValueError, match="Unsupported"):
        vs.ExperimentResult.load(path)


def test_same_custom_metric_name_in_multiple_scopes():
    env = environment()
    rec = env.add_controller(
        vs.Recorder(
            timeseries=False,
            custom_metrics={
                "cost": [
                    vs.Metric("EUR", microgrid="load"),
                    vs.Metric("EUR", microgrid="solar"),
                ],
            },
        )
    )
    env.run(60)
    assert rec.metrics["microgrids"]["load"]["cost"] == 0
    assert rec.metrics["microgrids"]["solar"]["cost"] == 0


def test_live_record_is_available_before_first_tick_and_finalized(tmp_path):
    env = vs.Environment.live()
    env.add_microgrid(
        [vs.Actor("load", vs.StaticSignal(-100))], dispatchables=[vs.GridConnection()]
    )
    rec = env.add_controller(vs.Recorder(tmp_path))

    class Inspect(vs.Controller):
        def start(self, environment):
            assert vs.ExperimentResult.load(tmp_path).execution["status"] == "running"

        def step(self, now, states):
            assert vs.ExperimentResult.load(tmp_path).execution["steps"] == 1

    env.add_controller(Inspect())
    env.run(0.01)
    assert vs.ExperimentResult.load(tmp_path).execution["status"] == "completed"
    assert rec.metrics["microgrids"]["microgrid_0"]["grid_import"] == pytest.approx(
        100 * 0.01 / 3600
    )


def test_memory_observations_stay_out_of_serialized_summary(tmp_path):
    env = environment()
    rec = env.add_controller(vs.Recorder())
    env.run(120)
    assert len(rec.log) == 2
    assert len(rec.to_df()) == 4
    rec.result.save(tmp_path / "summary.json")
    result = vs.ExperimentResult.load(tmp_path / "summary.json")
    assert result.timeseries is None
    assert result.metrics == rec.metrics
    assert list(tmp_path.iterdir()) == [tmp_path / "summary.json"]


@pytest.mark.parametrize("failure_source", ["controller", "signal", "metric"])
@pytest.mark.parametrize("recorder_first", [True, False])
def test_final_status_includes_all_cleanup_failures(tmp_path, failure_source, recorder_first):
    class BadCleanup(vs.Controller):
        def step(self, now, states):
            pass

        def finalize(self):
            raise RuntimeError("cleanup failed")

    class BadSignal(vs.StaticSignal):
        def finalize(self):
            raise RuntimeError("cleanup failed")

    class BadMetric(vs.Metric):
        def finalize(self):
            raise RuntimeError("cleanup failed")

    env = vs.Environment("2026-01-01")
    signal = BadSignal(-100) if failure_source == "signal" else vs.StaticSignal(-100)
    env.add_microgrid([vs.Actor("load", signal)], dispatchables=[vs.GridConnection()])
    recorder = vs.Recorder(tmp_path / "main")
    other = (
        vs.Recorder(tmp_path / "other", custom_metrics={"bad": BadMetric("1")})
        if failure_source == "metric"
        else BadCleanup()
    )
    if failure_source == "signal":
        env.add_controller(recorder)
    else:
        for controller in [recorder, other] if recorder_first else [other, recorder]:
            env.add_controller(controller)
    with pytest.raises(RuntimeError, match="cleanup failed"):
        env.run(1)
    assert env.status == recorder.result.execution["status"] == "failed"
    assert vs.ExperimentResult.load(tmp_path / "main").execution["status"] == "failed"
    if failure_source == "metric":
        assert vs.ExperimentResult.load(tmp_path / "other").execution["status"] == "failed"


def test_publication_failure_updates_other_recorders(tmp_path, monkeypatch):
    env = environment()
    first = env.add_controller(vs.Recorder(tmp_path / "first"))
    second = env.add_controller(vs.Recorder(tmp_path / "second"))

    def fail():
        raise OSError("disk full")

    monkeypatch.setattr(second, "_publish", fail)
    with pytest.raises(OSError, match="disk full"):
        env.run(1)
    assert (
        env.status
        == first.result.execution["status"]
        == second.result.execution["status"]
        == "failed"
    )
    assert vs.ExperimentResult.load(tmp_path / "first").execution["status"] == "failed"


def test_csv_preserves_identifier_strings_and_distinct_nested_fields(tmp_path):
    class NestedActor(vs.Actor):
        def state(self, elapsed):
            return {"b": {"power": 7}, "power": -10, "literal.key": 3, "literal%2Ekey": 4}

    env = vs.Environment("2026-01-01")
    for name in ("123", "true", "NA"):
        env.add_microgrid(
            [
                vs.Actor("a.b", vs.StaticSignal(-100)),
                NestedActor("a", vs.StaticSignal(-10)),
            ],
            name=name,
            dispatchables=[vs.GridConnection()],
        )
    rec = env.add_controller(vs.Recorder(tmp_path))
    env.run(1)
    frame = rec.to_df()
    assert list(frame.index.get_level_values("microgrid")) == ["123", "true", "NA"]
    row = frame.iloc[0]
    assert row["actor_states.a%2Eb.power"] == -100
    assert row["actor_states.a.b.power"] == 7
    assert row["actor_states.a.literal%2Ekey"] == 3
    assert row["actor_states.a.literal%252Ekey"] == 4


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, "12"])
def test_attached_metrics_reject_invalid_values_without_mutation(value):
    env = environment()
    rec = env.add_controller(vs.Recorder(timeseries=False))
    env.run(1)
    before = rec.result.to_dict()
    with pytest.raises(ValueError, match="finite number"):
        rec.result.add_metric("bad", value, "EUR")
    assert rec.result.to_dict() == before


def test_attached_metrics_validate_scope_and_do_not_replace_existing_values():
    env = environment()
    rec = env.add_controller(vs.Recorder(timeseries=False))
    env.run(1)
    result = rec.result
    for kwargs in ({"microgrid": "missing"}, {"microgrid": "load", "actor": "missing"}):
        with pytest.raises(ValueError, match="Unknown scope"):
            result.add_metric("cost", 1, "EUR", **kwargs)
    with pytest.raises(ValueError, match="requires a microgrid"):
        result.add_metric("cost", 1, "EUR", actor="load")
    with pytest.raises(ValueError, match="already exists"):
        result.add_metric("grid_import", 1, "Wh", microgrid="load")
    result.add_metric("undefined", None, "1")
    assert result.to_dict()["metrics"]["run"]["undefined"] is None


@pytest.mark.parametrize("source", ["actor", "grid_signal", "policy"])
@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_runtime_inputs_fail_instead_of_recording_zero(tmp_path, source, value):
    class BadSignal(vs.Signal):
        def at(self, elapsed=None):
            return value

    class BadPolicy(vs.DefaultDispatchPolicy):
        def apply(self, *args, **kwargs):
            kwargs["dispatchables"][0].current_power = value

    env = vs.Environment("2026-01-01")
    env.add_microgrid(
        [vs.Actor("load", BadSignal() if source == "actor" else vs.StaticSignal(-60))],
        grid_signals={"price": BadSignal()} if source == "grid_signal" else None,
        policy=BadPolicy() if source == "policy" else None,
        dispatchables=[vs.GridConnection()],
    )
    recorder = env.add_controller(vs.Recorder(tmp_path, timeseries=False))
    with pytest.raises(ValueError, match="finite"):
        env.run(60)
    assert recorder.steps == 0
    assert vs.ExperimentResult.load(tmp_path).execution["status"] == "failed"
