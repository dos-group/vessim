import pytest
from datetime import datetime
import pandas as pd
import tempfile
import os
import csv
from vessim.controller import MemoryLogger, CsvLogger
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
            "storage_state": {"soc": 0.5},
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


class TestCsvLogger:
    @pytest.fixture
    def temp_file(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            path = f.name
        yield path
        if os.path.exists(path):
            os.remove(path)

    def test_step_writes_csv(self, temp_file):
        logger = CsvLogger(temp_file)
        now = datetime(2023, 1, 1, 12, 0)
        state: MicrogridState = {
            "p_delta": 10.0,
            "p_grid": 5.0,
            "actor_states": {"actor1": {"power": 2}},
            "policy_state": {},
            "storage_state": None,
            "grid_signals": None,
        }

        logger.step(now, {"mg1": state})

        with open(temp_file, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        assert rows[0]["microgrid"] == "mg1"
        assert rows[0]["time"] == str(now)
        assert float(rows[0]["p_delta"]) == 10.0
        assert float(rows[0]["actor_states.actor1.power"]) == 2.0

    def test_step_appends_csv(self, temp_file):
        logger = CsvLogger(temp_file)
        now1 = datetime(2023, 1, 1, 12, 0)
        now2 = datetime(2023, 1, 1, 12, 1)
        state: MicrogridState = {
            "p_delta": 10.0,
            "p_grid": 5.0,
            "actor_states": {},
            "policy_state": {},
            "storage_state": None,
            "grid_signals": None,
        }

        logger.step(now1, {"mg1": state})
        logger.step(now2, {"mg1": state})

        with open(temp_file, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2
        assert rows[0]["time"] == str(now1)
        assert rows[1]["time"] == str(now2)
