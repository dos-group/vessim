"""Keep benchmark entry points runnable as simulation and recording APIs evolve."""

import json
from pathlib import Path
import subprocess
import sys

from benchmarks.run import CASES, environment_info

ROOT = Path(__file__).resolve().parents[1]


def run_benchmark(script, *args):
    result = subprocess.run(
        [sys.executable, str(ROOT / "benchmarks" / script), *map(str, args)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr


def test_workloads_repeat_csv_recording_and_profile_each_case(tmp_path):
    output = tmp_path / "reports/native.json"
    profiles = tmp_path / "profiles"
    run_benchmark(
        "run.py", "--steps", 6, "--repeats", 2, "--output", output, "--profile", profiles
    )
    report = json.loads(output.read_text())
    assert set(report["cases"]) == set(CASES)
    assert {p.stem for p in profiles.glob("*.prof")} == set(CASES)
    for case in report["cases"].values():
        assert len(case["runs"]) == 2
        assert len(case["trajectory_sha256"]) == 64
    assert (
        report["cases"]["csv"]["trajectory_sha256"]
        == report["cases"]["traces"]["trajectory_sha256"]
    )


def test_study_inputs_cover_both_throughput_and_memory_horizons(tmp_path):
    output = tmp_path / "reports/studies.json"
    run_benchmark(
        "studies.py",
        "--runs",
        2,
        "--steps",
        150,
        "--memory-steps",
        30,
        180,
        "--output",
        output,
    )
    report = json.loads(output.read_text())
    assert report["scenarios_per_second"] > 0
    assert {(row["output"], row["steps"]) for row in report["memory"]} == {
        (mode, steps) for mode in ("none", "metrics", "trajectory") for steps in (30, 180)
    }


def test_native_metadata_does_not_require_mosaik(monkeypatch):
    from importlib import metadata

    version = metadata.version

    def without_mosaik(package):
        if package == "mosaik":
            raise metadata.PackageNotFoundError(package)
        return version(package)

    monkeypatch.setattr(metadata, "version", without_mosaik)
    assert environment_info()["mosaik"] is None
