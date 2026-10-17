import pandas as pd
import pytest

import vessim as vs


def test_in_memory_record_and_dataframe(tmp_path):
    env = vs.Environment("2026-01-01", step_size=60)
    env.add_microgrid([vs.Actor("load", -100)], name="site", dispatchables=[vs.GridConnection()])
    rec = env.add_controller(vs.Recorder())
    env.run(120)
    frame = rec.to_df()
    assert isinstance(frame, pd.DataFrame)
    assert len(frame) == 2
    assert frame.index.names == ["time", "microgrid"]
    assert frame.iloc[0]["p_grid"] == -100
    assert len(rec.log) == 2
    assert rec.result.timeseries is None
    rec.result.save(tmp_path / "experiment.json")
    loaded = vs.ExperimentResult.load(tmp_path)
    assert loaded.timeseries is None
    assert loaded.metrics == rec.metrics


def test_no_trajectory_means_no_dataframe():
    env = vs.Environment("2026-01-01")
    env.add_microgrid([vs.Actor("load", -100)], dispatchables=[vs.GridConnection()])
    rec = env.add_controller(vs.Recorder(timeseries=False))
    env.run(1)
    with pytest.raises(RuntimeError, match="disabled"):
        rec.to_df()
