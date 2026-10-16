"""Experiment records and the shared validation boundary for persisted results."""

from __future__ import annotations

import json
import math
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np


def _json_default(value):
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (datetime, Path)):
        return str(value)
    raise TypeError(f"Experiment data must be JSON-compatible, got {type(value).__name__}.")


def _reject_constant(value: str):
    raise ValueError(f"Nonfinite JSON number: {value}")


def read_json(path: Path):
    """Read strict JSON; validation also rejects numeric overflow such as 1e999."""
    return json.loads(path.read_text(), parse_constant=_reject_constant)


def _object(value, label: str) -> dict:
    if not isinstance(value, dict) or any(not isinstance(k, str) for k in value):
        raise ValueError(f"{label} must be an object with string keys")
    return value


def _definition(value, label: str) -> None:
    definition = _object(value, label)
    if not isinstance(definition.get("unit"), str) or not definition["unit"]:
        raise ValueError(f"{label}.unit must be a nonempty string")
    if "description" in definition and not isinstance(definition["description"], str):
        raise ValueError(f"{label}.description must be a string")
    if "assumptions" in definition:
        _object(definition["assumptions"], f"{label}.assumptions")


def _metric_value(value, label: str) -> None:
    if value is not None and (
        isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
    ):
        raise ValueError(f"Metric '{label}' must be a finite number or None")


def validate_record(raw: dict) -> None:
    """Validate the same experiment contract for Python and the viewer catalog."""
    _object(raw, "Experiment")
    if (
        raw.get("format") != "vessim.experiment"
        or type(raw.get("schema_version")) is not int
        or raw["schema_version"] != 1
    ):
        raise ValueError("Unsupported Vessim experiment format or schema version.")
    if not isinstance(raw.get("run_id"), str) or not raw["run_id"]:
        raise ValueError("run_id must be a nonempty string")
    for name in ("config", "parameters", "execution", "metrics", "metric_definitions"):
        _object(raw.get(name), name)
    _object(raw["config"].get("microgrids"), "config.microgrids")
    execution = raw["execution"]
    if execution.get("status") not in ("running", "completed", "failed", "interrupted", "closed"):
        raise ValueError("execution.status is invalid")
    for name in ("steps", "simulated_duration", "wall_time", "until"):
        value = execution.get(name)
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            raise ValueError(f"execution.{name} must be nonnegative and finite or null")
    if execution.get("steps") is not None and type(execution["steps"]) is not int:
        raise ValueError("execution.steps must be an integer")

    def check_scope(values, definitions, depth, label):
        _object(values, label)
        _object(definitions, f"Definitions for {label}")
        if values.keys() != definitions.keys():
            raise ValueError(f"Metrics and definitions must have matching keys at {label}")
        for name, value in values.items():
            if not name:
                raise ValueError(f"Empty name at {label}")
            if depth:
                check_scope(value, definitions[name], depth - 1, f"{label}.{name}")
            else:
                _metric_value(value, f"{label}.{name}")
                _definition(definitions[name], f"{label}.{name}")

    for scope, depth in (("run", 0), ("microgrids", 1), ("actors", 2)):
        check_scope(raw["metrics"].get(scope), raw["metric_definitions"].get(scope), depth, scope)
    if "timeseries" not in raw:
        raise ValueError("timeseries must be a relative CSV path or null")
    trajectory = raw["timeseries"]
    if trajectory is not None and (
        not isinstance(trajectory, str)
        or not trajectory
        or Path(trajectory).is_absolute()
        or Path(trajectory).suffix.lower() != ".csv"
    ):
        raise ValueError("timeseries must be a relative CSV path or null")
    # Check every metadata value, including overflow parsed from valid JSON syntax.
    json.dumps(raw, allow_nan=False)


@dataclass
class ExperimentResult:
    """A summary with scoped metrics and an optional relative CSV reference.

    In-memory observations belong to Recorder.log, never to the persisted JSON.
    Loaded and recorded results remember their trajectory directory. Saving to
    another directory copies the CSV alongside the new JSON without changing
    the original result.
    """

    run_id: str
    config: dict
    parameters: dict
    execution: dict
    metrics: dict
    metric_definitions: dict
    timeseries: Optional[str]
    _directory: Optional[Path] = field(default=None, repr=False, compare=False)

    def to_dict(self) -> dict:
        """Return a detached, validated JSON-compatible summary."""
        raw = {
            "format": "vessim.experiment",
            "schema_version": 1,
            "run_id": self.run_id,
            "config": self.config,
            "parameters": self.parameters,
            "execution": self.execution,
            "metrics": self.metrics,
            "metric_definitions": self.metric_definitions,
            "timeseries": self.timeseries,
        }
        data = json.loads(json.dumps(raw, allow_nan=False, default=_json_default))
        validate_record(data)
        return data

    @property
    def timeseries_path(self) -> Optional[Path]:
        """Absolute path to the recorded CSV, or None when no CSV was recorded."""
        if self.timeseries is None:
            return None
        if self._directory is None:
            raise ValueError("CSV origin is unknown. Load the result from its JSON file.")
        return (self._directory / self.timeseries).resolve()

    def save(self, path: str | Path) -> None:
        """Save JSON atomically; copy a referenced CSV when exporting elsewhere.

        The copied CSV is named <JSON stem>.timeseries.csv. Saving in the source
        directory keeps the existing reference. In-memory recordings save only
        their summary; use Recorder(output=...) to persist their trajectory.
        """
        path = Path(path).resolve()
        data = self.to_dict()
        source = self.timeseries_path
        if source == path:
            raise ValueError("The JSON destination must not overwrite its CSV trajectory")
        if source is not None and path.parent != self._directory:
            target = path.with_name(path.stem + ".timeseries.csv")
            if target == path:
                raise ValueError("The JSON and CSV destinations must be different")
            path.parent.mkdir(parents=True, exist_ok=True)
            if source != target:
                temporary_csv = target.with_name(target.name + ".tmp")
                shutil.copyfile(source, temporary_csv)
                temporary_csv.replace(target)
            data["timeseries"] = target.name
        content = json.dumps(data, indent=2, allow_nan=False) + "\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(content)
        temporary.replace(path)

    @classmethod
    def load(cls, path: str | Path) -> ExperimentResult:
        """Load and validate an experiment JSON or directory, retaining its origin."""
        path = Path(path).resolve()
        if path.is_dir():
            path /= "experiment.json"
        raw = read_json(path)
        validate_record(raw)
        return cls(
            **{
                name: raw[name]
                for name in (
                    "run_id",
                    "config",
                    "parameters",
                    "execution",
                    "metrics",
                    "metric_definitions",
                    "timeseries",
                )
            },
            _directory=path.parent,
        )

    def add_metric(
        self,
        name: str,
        value: Optional[float],
        unit: str,
        *,
        microgrid: Optional[str] = None,
        actor: Optional[str] = None,
        description: str = "",
        assumptions: Optional[dict] = None,
    ) -> None:
        """Attach a scalar after the run; call save() to persist the updated record.

        Names must be new within their scope. Compute derived values in ordinary
        Python before calling this method; no calculator dependencies are inferred.
        """
        if self.execution["status"] == "running":
            raise RuntimeError("Add scalar metrics after the run has finished")
        if not isinstance(name, str) or not name:
            raise ValueError("Metric names must be nonempty strings")
        if actor is not None and microgrid is None:
            raise ValueError("An actor metric requires a microgrid name")
        definition = {"unit": unit, "description": description, "assumptions": assumptions or {}}
        definition = json.loads(json.dumps(definition, allow_nan=False, default=_json_default))
        _definition(definition, name)
        value = _json_default(value) if isinstance(value, np.generic) else value
        _metric_value(value, name)
        try:
            values, definitions = self.metrics, self.metric_definitions
            path = (
                ["actors", microgrid, actor]
                if actor is not None
                else ["microgrids", microgrid] if microgrid is not None else ["run"]
            )
            for key in path:
                values, definitions = values[key], definitions[key]
        except KeyError as exc:
            raise ValueError(f"Unknown scope for metric '{name}'") from exc
        if name in values:
            raise ValueError(f"Metric '{name}' already exists in this scope")
        values[name], definitions[name] = value, definition
