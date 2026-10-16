"""A shared experiment format for live experiments and simulation studies."""

from __future__ import annotations

import math
import time
from copy import deepcopy
from csv import DictWriter
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional, TextIO
from uuid import uuid4


from vessim._experiment import ExperimentResult
from vessim._util import flatten_dict
from vessim.controller import Controller, _build_experiment_config
from vessim.metrics import Metric

if TYPE_CHECKING:
    from vessim.environment import Environment
    from vessim.microgrid import MicrogridState


def _scopes(environment: Environment) -> dict:
    return {
        "run": {},
        "microgrids": {name: {} for name in environment.microgrids},
        "actors": {
            name: {actor.name: {} for actor in grid.actors}
            for name, grid in environment.microgrids.items()
        },
    }


def _scope(data: dict, metric: Metric) -> dict:
    if metric.actor is not None:
        return data["actors"][metric.microgrid][metric.actor]
    if metric.microgrid is not None:
        return data["microgrids"][metric.microgrid]
    return data["run"]


_ENERGY_DEFINITIONS = {
    "energy_produced": {
        "unit": "Wh",
        "description": "Positive actor power integrated over recorded intervals",
    },
    "energy_consumed": {
        "unit": "Wh",
        "description": "Absolute negative actor power integrated over recorded intervals",
    },
}
_GRID_DEFINITIONS = {
    **_ENERGY_DEFINITIONS,
    "grid_import": {"unit": "Wh", "description": "Imported grid energy over recorded intervals"},
    "grid_export": {"unit": "Wh", "description": "Exported grid energy over recorded intervals"},
    "peak_grid_import": {"unit": "W", "description": "Maximum sampled grid import power"},
    "peak_grid_export": {"unit": "W", "description": "Maximum sampled grid export power"},
}


class Recorder(Controller):
    """Record an experiment with metrics and time series enabled by default.

    With output set, time series stream to CSV without being retained in memory.
    Otherwise they remain in memory and are accessible through log and to_df().
    Set timeseries=False for bounded-memory studies. Study metadata is written
    once at completion. Live output is refreshed each tick by default.

    Args:
        output: Experiment directory for experiment.json and optional timeseries.csv.
        metrics: Collect standard physical metrics (default True).
        timeseries: Collect detailed observations (default True).
        custom_metrics: Named Metric instances, extending the standard metrics.
            A list under one name registers that metric in several scopes.
            Instances must belong to one recorder and names must be unique in scope.
        parameters: User-supplied scenario parameters, including seeds if relevant.
        run_id: Identifier for joining results to a study. Generated when omitted.
        flush: Override per-tick publication (defaults to the environment's live mode).
    """

    def __init__(
        self,
        output: Optional[str | Path] = None,
        *,
        metrics: bool = True,
        timeseries: bool = True,
        custom_metrics: Optional[dict[str, Metric | list[Metric]]] = None,
        parameters: Optional[dict] = None,
        run_id: Optional[str] = None,
        flush: Optional[bool] = None,
    ):
        self.output = Path(output) if output is not None else None
        self.collect_metrics = metrics
        self.collect_timeseries = timeseries
        self.custom_metrics = dict(custom_metrics or {})
        self.parameters = deepcopy(parameters or {})
        self.run_id = run_id if run_id is not None else uuid4().hex
        self.flush = flush
        self.log: dict[datetime, dict[str, MicrogridState]] = {}
        self._result: Optional[ExperimentResult] = None
        self._file: Optional[TextIO] = None
        self._writer: Optional[DictWriter] = None
        self._started_metrics: list[tuple[str, Metric]] = []
        self._finalized = False
        self.steps = 0
        self.duration = 0.0

    @property
    def result(self) -> ExperimentResult:
        """The experiment record, available after start and finalized after run."""
        if self._result is None:
            raise RuntimeError("Recorder must be started by an Environment first.")
        return self._result

    @property
    def metrics(self) -> dict:
        """Scoped numeric values, including completed custom metrics after run."""
        return self.result.metrics

    @property
    def csv_path(self) -> Path:
        """The on-disk trajectory path, when output is configured."""
        if self.output is None:
            raise RuntimeError("This recorder has no output directory.")
        return self.output / "timeseries.csv"

    def start(self, environment: Environment) -> None:
        """Capture configuration and initialize metric calculators."""
        if self._result is not None:
            raise RuntimeError("A Recorder is single-use. Create one for each experiment.")
        self._environment = environment
        self._started = time.perf_counter()
        self._flush = environment.is_live if self.flush is None else self.flush
        trajectory = (
            "timeseries.csv" if self.collect_timeseries and self.output is not None else None
        )
        self._result = ExperimentResult(
            run_id=self.run_id,
            config=_build_experiment_config(environment),
            parameters=deepcopy(self.parameters),
            execution={
                "status": "running",
                "start": datetime.now().isoformat(),
                "end": None,
                "wall_time": None,
                "steps": 0,
                "simulated_duration": 0.0,
                "until": environment.until if math.isfinite(environment.until) else None,
                "last_time": None,
            },
            metrics=_scopes(environment),
            metric_definitions=_scopes(environment),
            timeseries=trajectory,
            _directory=self.output.resolve() if self.output is not None else None,
        )
        if self.collect_metrics:
            for name, grid in environment.microgrids.items():
                self.metrics["microgrids"][name] = {key: 0.0 for key in _GRID_DEFINITIONS}
                self.result.metric_definitions["microgrids"][name] = deepcopy(_GRID_DEFINITIONS)
                for actor in grid.actors:
                    self.metrics["actors"][name][actor.name] = {
                        key: 0.0 for key in _ENERGY_DEFINITIONS
                    }
                    self.result.metric_definitions["actors"][name][actor.name] = deepcopy(
                        _ENERGY_DEFINITIONS
                    )
        seen = set()
        registrations = [
            (name, metric)
            for name, calculators in self.custom_metrics.items()
            for metric in (calculators if isinstance(calculators, list) else [calculators])
        ]
        for name, metric in registrations:
            if not isinstance(name, str) or not name or not isinstance(metric, Metric):
                raise ValueError("custom_metrics must map nonempty names to Metric instances.")
            if id(metric) in seen:
                raise ValueError("A Metric instance can only be registered once.")
            seen.add(id(metric))
            try:
                values = _scope(self.metrics, metric)
                definitions = _scope(self.result.metric_definitions, metric)
            except KeyError as exc:
                raise ValueError(f"Unknown scope for custom metric '{name}'.") from exc
            if name in values:
                raise ValueError(f"Metric '{name}' already exists in this scope.")
            values[name] = None
            definitions[name] = deepcopy(metric.definition())
            metric.start(environment)
            self._started_metrics.append((name, metric))
        # Reject invalid metadata before beginning the simulation.
        self.result.to_dict()
        if self.output is not None:
            self.output.mkdir(parents=True, exist_ok=True)
            if self.collect_timeseries:
                self._file = self.csv_path.open("w", newline="")
            if self._flush:
                self._publish()

    def step(self, now: datetime, microgrid_states: dict[str, MicrogridState]) -> None:
        """Accumulate an interval and optionally retain or stream its observation."""
        env = self._environment
        assert env.sim_start is not None
        elapsed = (now - env.sim_start).total_seconds()
        duration = min(env.step_size, env.until - elapsed)
        self.steps += 1
        self.duration += duration
        self.result.execution.update(
            {
                "steps": self.steps,
                "simulated_duration": self.duration,
                "last_time": now,
            }
        )
        if self.collect_metrics:
            self._physical_metrics(microgrid_states, duration)
        for _, metric in self._started_metrics:
            metric.step(now, microgrid_states, duration)
        if self.collect_timeseries:
            if self.output is None:
                # Runtime observations are already detached from component state.
                self.log[now] = microgrid_states
            else:
                rows = [
                    {"microgrid": name, "time": now, **flatten_dict(dict(state))}
                    for name, state in microgrid_states.items()
                ]
                if self._writer is None:
                    fields = list(dict.fromkeys(key for row in rows for key in row))
                    assert self._file is not None
                    self._writer = DictWriter(self._file, fieldnames=fields)
                    self._writer.writeheader()
                self._writer.writerows(rows)
        if self._flush and self.output is not None:
            if self._file is not None:
                self._file.flush()
            self._publish()

    def _physical_metrics(self, states: dict[str, MicrogridState], duration: float) -> None:
        hours = duration / 3600
        metrics = self.metrics
        for name, state in states.items():
            values = metrics["microgrids"][name]
            imported, exported = max(0.0, -state["p_grid"]), max(0.0, state["p_grid"])
            values["grid_import"] += imported * hours
            values["grid_export"] += exported * hours
            values["peak_grid_import"] = max(values["peak_grid_import"], imported)
            values["peak_grid_export"] = max(values["peak_grid_export"], exported)
            # Use the sampled powers used by dispatch, even when a custom actor's
            # state() omits power or exposes a different diagnostic value.
            for actor, power in self._environment.microgrids[name]._powers.items():
                produced, consumed = max(0.0, power) * hours, max(0.0, -power) * hours
                actor_values = metrics["actors"][name][actor]
                actor_values["energy_produced"] += produced
                actor_values["energy_consumed"] += consumed
                values["energy_produced"] += produced
                values["energy_consumed"] += consumed

    def finalize(self) -> None:
        """Close the CSV and finalize independent metrics; Environment publishes afterward."""
        if self._result is None or self._finalized:
            return
        self._finalized = True
        errors: list[BaseException] = []
        if self._file is not None:
            try:
                self._file.close()
            except BaseException as exc:
                errors.append(exc)
            self._file = None
        for name, metric in self._started_metrics:
            try:
                value = metric.finalize()
                if value is not None:
                    value = float(value)
                    if not math.isfinite(value):
                        raise ValueError(f"Metric '{name}' must return a finite value or None.")
                _scope(self.metrics, metric)[name] = value
            except BaseException as exc:
                errors.append(exc)
        if errors:
            self.result.execution["metric_error"] = str(errors[0])
            raise errors[0]

    def _complete(self) -> None:
        """Publish only after Environment has attempted all cleanup callbacks."""
        if self._result is None:
            return
        self.result.execution.update(
            {
                "status": self._environment.status,
                "end": datetime.now().isoformat(),
                "wall_time": time.perf_counter() - self._started,
            }
        )
        if self.output is not None:
            self._publish()

    def _publish(self) -> None:
        assert self.output is not None
        self.result.save(self.output / "experiment.json")

    def to_df(self):
        """Read the retained or saved trajectory as a pandas DataFrame."""
        import pandas as pd

        if not self.collect_timeseries:
            raise RuntimeError("Time series recording is disabled.")
        if self.output is not None:
            if self._file is not None:
                self._file.flush()
            try:
                frame = pd.read_csv(
                    self.csv_path,
                    parse_dates=["time"],
                    dtype={"microgrid": str},
                    keep_default_na=False,
                    na_values=[""],
                )
            except pd.errors.EmptyDataError:
                return pd.DataFrame()
        else:
            frame = pd.DataFrame(
                [
                    {"time": now, "microgrid": name, **flatten_dict(state)}
                    for now, states in self.log.items()
                    for name, state in states.items()
                ]
            )
        return frame.set_index(["time", "microgrid"]) if not frame.empty else frame
