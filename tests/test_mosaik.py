import sys
from pathlib import Path

import pytest

pytest.importorskip("mosaik")

import vessim as vs

SIMULATOR = Path(__file__).parent / "simulators/power_source.py"
# Importable in-process and separately executable using the same simulator API.
sys.path.insert(0, str(SIMULATOR.parent))


@pytest.mark.parametrize("live", [False, True])
@pytest.mark.parametrize("source_name", ["Source", "Vessim"])
def test_external_power_and_delayed_feedback(live, source_name, tmp_path):
    create = vs.Environment.live if live else vs.Environment
    env = create(
        sim_start="2026-01-01",
        backend="mosaik",
        sim_config={
            source_name: {"python": "power_source:PowerSource"},
        },
    )
    marker = tmp_path / "closed"
    records = []
    with env:
        source = env.world.start(source_name, marker=str(marker), records=records).Source()
        env.add_microgrid([], name="external", dispatchables=[vs.GridConnection()])
        log = env.add_controller(vs.Recorder(metrics=False))
        env.prepare()
        entity = env.entities["external"]
        env.world.connect(source, entity, "power")
        env.world.connect(
            entity, source, ("p_grid", "feedback"), time_shifted=True, initial_data={"p_grid": 0}
        )
        env.run(2)
    assert [row["external"]["p_grid"] for row in log.log.values()] == [100, 201]
    assert records == [(0, 0), (1, 100)]
    assert marker.read_text() == "finalized"


def test_external_slower_sampling_and_cleanup(tmp_path):
    env = vs.Environment(
        "2026-01-01",
        backend="mosaik",
        sim_config={
            "Source": {"python": "power_source:PowerSource"},
        },
    )
    marker = tmp_path / "closed"
    with env:
        source = env.world.start("Source", marker=str(marker), period=2).Source()
        env.add_microgrid([], name="external", dispatchables=[vs.GridConnection()])
        log = env.add_controller(vs.Recorder(metrics=False))
        env.prepare()
        env.world.connect(source, env.entities["external"], "power")
        env.run(5)
    assert [row["external"]["p_grid"] for row in log.log.values()] == [100, 100, 102, 102, 104]
    assert marker.exists()


def test_external_failure_and_setup_failure_cleanup(tmp_path):
    for fail_setup in (False, True):
        marker = tmp_path / str(fail_setup)
        with pytest.raises(RuntimeError):
            with vs.Environment(
                "2026-01-01",
                backend="mosaik",
                sim_config={
                    "Source": {"python": "power_source:PowerSource"},
                },
            ) as env:
                source = env.world.start("Source", marker=str(marker), failure=True).Source()
                if fail_setup:
                    raise RuntimeError("setup failed")
                env.add_microgrid([], name="external", dispatchables=[vs.GridConnection()])
                env.prepare()
                env.world.connect(source, env.entities["external"], "power")
                env.run(3)
        assert marker.exists()


def test_remote_process_coupling(tmp_path):
    marker = tmp_path / "remote_closed"
    with vs.Environment(
        "2026-01-01",
        backend="mosaik",
        sim_config={
            "Remote": {"cmd": f'"{sys.executable}" "{SIMULATOR}" %(addr)s', "posix": True},
        },
    ) as env:
        source = env.world.start("Remote", marker=str(marker)).Source()
        env.add_microgrid([], name="external", dispatchables=[vs.GridConnection()])
        env.prepare()
        env.world.connect(source, env.entities["external"], "power")
        result = env.run(3)
    assert result.states["external"]["p_grid"] == 102
    assert marker.read_text() == "finalized"


def test_missing_external_input_is_explicit():
    env = vs.Environment("2026-01-01", backend="mosaik")
    env.add_microgrid([], name="external", dispatchables=[vs.GridConnection()])
    with pytest.raises(ValueError, match="requires external power"):
        env.run(1)


def test_unsupported_input_is_explicit():
    with vs.Environment(
        "2026-01-01",
        backend="mosaik",
        sim_config={
            "Source": {"python": "power_source:PowerSource"},
        },
    ) as env:
        source = env.world.start("Source").Source()
        env.add_microgrid(
            [vs.Actor("a", vs.StaticSignal(0))], name="grid", dispatchables=[vs.GridConnection()]
        )
        env.prepare()
        env.world.connect(source, env.entities["grid"], ("power", "policy_state"))
        with pytest.raises(ValueError, match="Only the 'power' input"):
            env.run(1)


def test_remote_sink_failure_at_last_tick_is_not_reported_as_success(tmp_path):
    marker = tmp_path / "sink_closed"
    env = vs.Environment(
        "2026-01-01",
        backend="mosaik",
        sim_config={
            "Sink": {"cmd": f'"{sys.executable}" "{SIMULATOR}" %(addr)s', "posix": True},
        },
    )
    with env:
        sink = env.world.start("Sink", marker=str(marker), failure=True).Source()
        env.add_microgrid(
            [vs.Actor("a", vs.StaticSignal(100))], name="grid", dispatchables=[vs.GridConnection()]
        )
        env.prepare()
        env.world.connect(env.entities["grid"], sink, ("p_grid", "feedback"))
        with pytest.raises(RuntimeError, match="all simulators completed"):
            env.run(2)
    assert env.status == "failed"
    assert marker.exists()
