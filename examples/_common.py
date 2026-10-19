"""Small file helpers shared by the runnable examples."""

import json
from pathlib import Path


def fresh_output(path: Path) -> Path:
    """Keep each invocation separate from previous results."""
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise FileExistsError(f"Output is not empty: {path}. Choose a fresh --output directory.")
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_study(output, study_id, name, groups, *, run_parameters=(), description=""):
    """Write explicit configuration membership alongside canonical run records.

    Each group is (configuration ID, display name, run IDs). Runs live directly
    below the output directory. No results or parameters are copied into the index.
    """
    document = {
        "format": "vessim.study",
        "schema_version": 2,
        "study_id": study_id,
        "name": name,
        "description": description,
        "run_parameters": list(run_parameters),
        "configurations": [
            {
                "configuration_id": identity,
                "name": label,
                "runs": [{"path": f"{run_id}/experiment.json"} for run_id in runs],
            }
            for identity, label, runs in groups
        ],
    }
    (output / "study.json").write_text(json.dumps(document, indent=2, allow_nan=False) + "\n")
