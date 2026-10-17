"""Read-only experiment catalog shared by the viewer server and static exports."""

from __future__ import annotations

import json
import shutil
from pathlib import Path


from vessim._experiment import read_json, validate_record


class Catalog:
    """Index summaries without reading referenced trajectories.

    Embedded study CSV references are relative to the study file. Standalone
    references are relative to their experiment JSON. References must remain
    within the opened directory (or the input file's parent).
    """

    def __init__(self, source: Path):
        self.source = source.resolve()
        self.root = self.source if self.source.is_dir() else self.source.parent
        self.trajectories: dict[str, Path] = {}
        self.runs: list[dict] = []
        self.errors: list[str] = []
        if not self.source.exists():
            raise ValueError(f"Input does not exist: {source}")
        if self.source.is_file():
            files = [self.source]
        elif (self.source / "experiment.json").is_file():
            files = [self.source / "experiment.json"]
        else:
            files = sorted(self.source.glob("*/experiment.json"))
        for file in files:
            self._read(file)

    def _read(self, file: Path) -> None:
        try:
            raw = read_json(file)
            if not isinstance(raw, dict) or raw.get("schema_version") != 1:
                raise ValueError("Unsupported format or schema version")
            if raw.get("format") == "vessim.study":
                records = raw.get("experiments")
                if not isinstance(records, list):
                    raise ValueError("Study experiments must be a list")
            else:
                records = [raw]
            for position, record in enumerate(records):
                try:
                    self._add(record, file)
                except (ValueError, TypeError, KeyError) as exc:
                    self.errors.append(f"{file.name}, record {position + 1}: {exc}")
        except (OSError, ValueError, TypeError) as exc:
            self.errors.append(f"{file.name}: {exc}")

    def _add(self, record: dict, file: Path) -> None:
        validate_record(record)
        key = str(len(self.runs))
        trajectory = record["timeseries"]
        if trajectory is not None:
            target = (file.parent / trajectory).resolve()
            if not target.is_relative_to(self.root):
                raise ValueError("Trajectory reference must stay within the opened results root")
            self.trajectories[key] = target
        summary = {k: v for k, v in record.items() if k != "timeseries"}
        self.runs.append(
            {
                "key": key,
                "source": str(file.relative_to(self.root)),
                "record": summary,
                "trajectory": (
                    {"url": f"data/{key}/trajectory"} if trajectory is not None else None
                ),
            }
        )

    def payload(self) -> dict:
        """Return the viewer transport envelope; canonical records remain unchanged."""
        return {
            "name": self.source.stem if self.source.is_file() else self.source.name,
            "runs": self.runs,
            "errors": list(self.errors),
        }

    def trajectory(self, key: str) -> tuple[bytes, str]:
        """Read a trajectory only when a user opens its charts."""
        return self.trajectories[key].read_bytes(), "text/csv; charset=utf-8"

    def export(self, destination: Path, assets: Path) -> None:
        """Create a portable static viewer, preserving lazy trajectory loading."""
        if destination.exists() and any(destination.iterdir()):
            raise ValueError("Static export destination must be empty")
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copytree(assets, destination, dirs_exist_ok=True)
        payload = self.payload()
        for key in self.trajectories:
            try:
                content, _ = self.trajectory(key)
                target = destination / "data" / key / "trajectory"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            except OSError as exc:
                payload["errors"].append(f"Trajectory for run {key} unavailable: {exc}")
        (destination / "catalog.json").write_text(json.dumps(payload, allow_nan=False))
