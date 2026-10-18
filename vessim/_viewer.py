"""Study catalogs shared by the local viewer, static reports and documentation."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Optional

from vessim._experiment import read_json, validate_record


class Catalog:
    """Load completed experiment summaries; read CSVs only when requested.

    Study v2 references are relative to the study file, batch references likewise.
    CSV references are relative to their experiment (or batch) file and must stay
    within that file's directory. Only explicitly registered files are served.
    """

    def __init__(self, source: Path, *, study_paths: Optional[list[Path]] = None):
        self.source = source.resolve()
        self.trajectories: dict[str, Path] = {}
        self.studies: list[dict] = []
        self.runs: list[dict] = []
        self.errors: list[str] = []
        if not self.source.exists():
            raise ValueError(f"Input does not exist: {source}")
        if study_paths is not None:
            files = study_paths
        elif self.source.is_file():
            files = [self.source]
        elif (self.source / "study.json").is_file():
            files = [self.source / "study.json"]
        elif (self.source / "experiment.json").is_file():
            files = [self.source / "experiment.json"]
        else:
            files = sorted(self.source.glob("*/study.json"))
            if not files:
                files = sorted(self.source.glob("*/experiment.json"))
                self._collection(files)
                return
        for file in files:
            try:
                raw = read_json(file)
                if raw.get("format") == "vessim.study":
                    self._study(raw, file)
                elif raw.get("format") == "vessim.experiment":
                    self._collection([file])
                else:
                    raise ValueError("Expected vessim.study v2 or vessim.experiment v1")
            except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
                self.errors.append(f"{file.name}: {exc}")

    def _collection(self, files: list[Path]) -> None:
        study: dict = {
            "study_id": self.source.stem,
            "name": self.source.stem,
            "configurations": [],
            "errors": [],
        }
        seen: set[str] = set()
        for file in files:
            try:
                run = self._run(read_json(file), file, seen)
                if run is not None:
                    study["configurations"].append(
                        {"configuration_id": run["run_id"], "runs": [run]}
                    )
            except (OSError, ValueError, TypeError, KeyError) as exc:
                study["errors"].append(f"{file.parent.name}/{file.name}: {exc}")
        self._register(study)

    def _study(self, raw: dict, file: Path) -> None:
        if raw.get("schema_version") != 2 or not isinstance(raw.get("configurations"), list):
            raise ValueError("Expected vessim.study schema_version 2 with configurations")
        identity = raw.get("study_id")
        if not isinstance(identity, str) or not identity:
            raise ValueError("study_id must be a nonempty string")
        if any(s["study_id"] == identity for s in self.studies):
            raise ValueError(f"Duplicate study_id: {identity}")
        run_parameters = raw.get("run_parameters", [])
        if not isinstance(run_parameters, list) or any(
            not isinstance(p, str) for p in run_parameters
        ):
            raise ValueError("run_parameters must be a list of parameter names")
        study = {**raw, "configurations": [], "errors": []}
        config_ids: set[str] = set()
        seen: set[str] = set()
        for config in raw["configurations"]:
            try:
                cid = config["configuration_id"]
                if not isinstance(cid, str) or not cid or cid in config_ids:
                    raise ValueError("Invalid or duplicate configuration_id")
                config_ids.add(cid)
                group = {"configuration_id": cid, "runs": []}
                if config.get("name"):
                    group["name"] = str(config["name"])
                if "run_batch" in config:
                    if "runs" in config:
                        raise ValueError("Choose runs or run_batch, not both")
                    batch_file = self._reference(file, config["run_batch"])
                    batch = read_json(batch_file)
                    if (
                        batch.get("format") != "vessim.viewer.run-batch"
                        or batch.get("schema_version") != 1
                        or not isinstance(batch.get("runs"), list)
                    ):
                        raise ValueError("Unsupported run batch")
                    shared = batch["shared"]
                    for item in batch["runs"]:
                        record = {
                            **shared,
                            **item,
                            "parameters": {
                                **shared.get("parameters", {}),
                                **item.get("parameters", {}),
                            },
                        }
                        self._append(group, record, batch_file, seen, study)
                else:
                    if not isinstance(config.get("runs"), list):
                        raise ValueError("Configuration must contain runs or run_batch")
                    for reference in config["runs"]:
                        try:
                            origin = self._reference(file, reference["path"])
                            record = read_json(origin)
                            if reference.get("run_id") is not None and reference[
                                "run_id"
                            ] != record.get("run_id"):
                                raise ValueError("Run identity mismatch")
                            self._append(group, record, origin, seen, study)
                        except (OSError, ValueError, TypeError, KeyError) as exc:
                            study["errors"].append(f"{cid}: {exc}")
                if group["runs"]:
                    study["configurations"].append(group)
            except (OSError, ValueError, TypeError, KeyError) as exc:
                study["errors"].append(f"Configuration: {exc}")
        self._register(study)

    @staticmethod
    def _reference(origin: Path, reference: str) -> Path:
        if not isinstance(reference, str) or not reference or Path(reference).is_absolute():
            raise ValueError("References must be nonempty relative paths")
        return (origin.parent / reference).resolve()

    def _append(self, group, record, origin, seen, study):
        try:
            run = self._run(record, origin, seen)
            if run is not None:
                group["runs"].append(run)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            study["errors"].append(f"{group['configuration_id']}: {exc}")

    def _run(self, record: dict, origin: Path, seen: set[str]) -> Optional[dict]:
        validate_record(record)
        if record["execution"]["status"] != "completed":
            raise ValueError(f"Run {record['run_id']} is not completed")
        if record["run_id"] in seen:
            raise ValueError(f"Duplicate run_id: {record['run_id']}")
        trajectory = record["timeseries"]
        key = str(len(self.trajectories))
        url = None
        if trajectory is not None:
            target = self._reference(origin, trajectory)
            if not target.is_relative_to(origin.parent.resolve()):
                raise ValueError("Trajectory must stay within the experiment directory")
            self.trajectories[key] = target
            url = f"data/{key}/trajectory"
        seen.add(record["run_id"])
        # The catalog is transport, not another persisted experiment format.
        return {
            "run_id": record["run_id"],
            "record": {**record, "timeseries": None},
            "trajectoryUrl": url,
        }

    def _register(self, study: dict) -> None:
        self.studies.append(study)
        self.runs.extend(r for c in study["configurations"] for r in c["runs"])
        self.errors.extend(
            f"{study['name'] if 'name' in study else study['study_id']}: {e}"
            for e in study["errors"]
        )

    def payload(self) -> dict:
        """Return lightweight study choices without any run or trajectory data."""
        return {
            "studies": [
                {
                    "study_id": s["study_id"],
                    "name": s.get("name", s["study_id"]),
                    "url": f"data/{i}/study.json",
                }
                for i, s in enumerate(self.studies)
            ],
            "errors": list(self.errors),
        }

    def study(self, key: str) -> dict:
        """Return summaries and explicit configuration membership for one study."""
        if not key.isdecimal() or int(key) >= len(self.studies):
            raise KeyError(key)
        return self.studies[int(key)]

    def trajectory(self, key: str) -> tuple[bytes, str]:
        """Read a recording only when a user opens its charts."""
        return self.trajectories[key].read_bytes(), "text/csv; charset=utf-8"

    def export(self, destination: Path, assets: Path) -> None:
        """Create a portable report using the exact same catalog and interface."""
        if destination.exists() and any(destination.iterdir()):
            raise ValueError("Static export destination must be empty")
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copytree(assets, destination, dirs_exist_ok=True)
        payload = self.payload()
        for i, study in enumerate(self.studies):
            target = destination / "data" / str(i) / "study.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(study, allow_nan=False))
        for key in self.trajectories:
            try:
                content, _ = self.trajectory(key)
                target = destination / "data" / key / "trajectory"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            except OSError as exc:
                payload["errors"].append(f"Trajectory {key} unavailable: {exc}")
        (destination / "catalog.json").write_text(json.dumps(payload, allow_nan=False))
