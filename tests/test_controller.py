import pytest
from datetime import datetime
import pandas as pd
from vessim.controller import MemoryLogger
from vessim.microgrid import MicrogridState

class TestMemoryLogger:
    @pytest.fixture
    def logger(self):
        return MemoryLogger()

    @pytest.fixture
    def sample_data(self):
        now = datetime(2023, 1, 1, 12, 0)
        state: MicrogridState = {
            "p_delta": 10.0,
            "p_grid": 5.0,
            "actor_states": {"actor1": {"power": 2}},
            "policy_state": {"mode": "charge"},
            "dispatch_states": {"battery": {"soc": 0.5}},
            "grid_signals": {"co2": 100},
        }
        return now, {"mg1": state}

    def test_step_logs_data(self, logger, sample_data):
        now, states = sample_data
        logger.step(now, states)
        assert logger.log[now] == states

    def test_to_dict(self, logger, sample_data):
        now, states = sample_data
        logger.step(now, states)
        d = logger.to_dict()
        assert d[now] == states

    def test_to_df(self, logger, sample_data):
        now, states = sample_data
        logger.step(now, states)
        df = logger.to_df()

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        # Check index
        assert df.index[0] == (now, "mg1")
        # Check columns (flattened)
        assert df.loc[(now, "mg1")]["p_delta"] == 10.0
        assert df.loc[(now, "mg1")]["actor_states.actor1.power"] == 2
