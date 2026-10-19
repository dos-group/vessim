import subprocess
import os
import sys
import pytest
from pathlib import Path
import shutil
import json
import re

EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "examples")


def run_script(script_name, cwd=None, args=()):
    script_path = os.path.join(EXAMPLES_DIR, script_name)
    result = subprocess.run(
        [sys.executable, script_path, *args],
        capture_output=True,
        text=True,
        cwd=cwd or os.path.dirname(EXAMPLES_DIR),
    )
    return result


def test_basic_example(tmp_path):
    result = run_script("basic_example.py", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "Grid import: 26.71 kWh" in result.stdout
    assert "Grid export: 11.08 kWh" in result.stdout
    record = json.loads((tmp_path / "results/basic_example/experiment.json").read_text())
    assert record["execution"]["status"] == "completed"
    assert record["execution"]["steps"] == 864
    assert record["execution"]["simulated_duration"] == 3 * 24 * 3600
    assert record["metrics"]["microgrids"]["site"]["energy_consumed"] == pytest.approx(50400)


@pytest.mark.parametrize("document", ["README.md", "docs/getting_started.md"])
def test_first_use_documentation_runs_as_written(tmp_path, document):
    shutil.copy(
        Path(__file__).parents[1] / "datasets/solar_example.csv", tmp_path / "solar_example.csv"
    )
    source = (Path(__file__).parents[1] / document).read_text()
    code = "\n".join(re.findall(r"```python\n(.*?)```", source, re.S))
    for capacity, imported, exported in [(1000, "26.71", "11.08"), (2000, "24.71", "9.08")]:
        result = subprocess.run(
            [sys.executable, "-c", code.replace("capacity=1000", f"capacity={capacity}")],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert f"Grid import: {imported} kWh" in result.stdout
        assert f"Grid export: {exported} kWh" in result.stdout


def test_csv_walkthrough(tmp_path):
    guide = (Path(__file__).parents[1] / "docs/concepts/signals.md").read_text()
    data = re.findall(r"```csv\n(.*?)```", guide, re.S)[0]
    (tmp_path / "input.csv").write_text(data)
    script = Path(EXAMPLES_DIR).resolve() / "replay_csv.py"
    result = subprocess.run(
        [sys.executable, str(script), "input.csv", "--hours", "6"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "Grid import: 1.10 kWh" in result.stdout
    assert "Grid export: 1.70 kWh" in result.stdout


def test_battery_sizing_study_is_reproducible_across_workers(tmp_path):
    script = Path(EXAMPLES_DIR).resolve() / "battery_sizing_study.py"
    for workers in (1, 2):
        subprocess.run(
            [
                sys.executable,
                str(script),
                "--scenarios",
                "4",
                "--workers",
                str(workers),
                "--output",
                str(tmp_path / str(workers)),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    sequential = [
        json.loads((tmp_path / "1" / r["path"]).read_text())
        for c in json.loads((tmp_path / "1/study.json").read_text())["configurations"]
        for r in c["runs"]
    ]
    parallel = [
        json.loads((tmp_path / "2" / r["path"]).read_text())
        for c in json.loads((tmp_path / "2/study.json").read_text())["configurations"]
        for r in c["runs"]
    ]
    # Wall-clock execution timestamps differ, scientific results must not.
    for first, second in zip(sequential, parallel):
        for key in ("run_id", "parameters", "config", "metrics", "metric_definitions"):
            assert first[key] == second[key]
        assert first["execution"]["status"] == second["execution"]["status"] == "completed"


def test_external_simulator_coupling(tmp_path):
    pytest.importorskip("mosaik")
    result = run_script("external_simulator_coupling.py", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "grid_import" in result.stdout


def test_live_server_monitoring(tmp_path):
    pytest.importorskip("fastapi")
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from threading import Thread
    import socket
    import json

    class Prometheus(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps(
                {
                    "status": "success",
                    "data": {
                        "result": [{"value": [0, "100"]}],
                    },
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Prometheus)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        broker_port = sock.getsockname()[1]
    try:
        result = subprocess.run(
            [
                sys.executable,
                os.path.join(EXAMPLES_DIR, "live_server_monitoring.py"),
                "--prometheus-url",
                f"http://127.0.0.1:{server.server_port}",
                "--broker-port",
                str(broker_port),
                "--until",
                "0.1",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0, result.stderr
        assert "API broker terminated" in result.stdout
    finally:
        server.shutdown()
        worker.join()
        server.server_close()


def test_custom_metrics_example(tmp_path):
    result = run_script("custom_metrics.py", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "Objectives:" in result.stdout
    with (tmp_path / "results/custom_metrics/experiment.json").open() as file:
        record = json.load(file)
    assert record["timeseries"] is None
    assert record["metrics"]["actors"]["site"]["solar"]["area"] == 25
    assert record["execution"]["status"] == "completed"


def test_demand_response_example(tmp_path):
    result = run_script("demand_response.py", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "00:00:00: 1000 W",
        "00:01:00: 700 W",
        "00:02:00: 700 W",
        "00:03:00: 1000 W",
    ]


@pytest.mark.parametrize(
    "script, options",
    [
        ("basic_example.py", []),
        ("replay_csv.py", []),
        ("custom_metrics.py", []),
        ("demand_response.py", []),
        ("strategy_comparison.py", ["--scenarios", "2"]),
        ("microgrid_comparison.py", ["--days", "1"]),
        ("infrastructure_study.py", ["--days", "1", "--trials", "12"]),
    ],
)
def test_examples_reproduce_recorded_results_and_keep_existing_output(tmp_path, script, options):
    if "--trials" in options:
        pytest.importorskip("optuna")
    outputs = [tmp_path / "first", tmp_path / "second"]
    for output in outputs:
        result = run_script(script, cwd=tmp_path, args=[*options, "--output", str(output)])
        assert result.returncode == 0, result.stderr
    first = sorted(outputs[0].rglob("experiment.json"))
    assert first
    for file in first:
        relative = file.relative_to(outputs[0])
        a, b = json.loads(file.read_text()), json.loads((outputs[1] / relative).read_text())
        for field in ("run_id", "parameters", "config", "metrics", "metric_definitions"):
            assert a[field] == b[field], (script, relative, field)
        for field in ("status", "steps", "simulated_duration"):
            assert a["execution"][field] == b["execution"][field]
        csv = file.parent / "timeseries.csv"
        if csv.exists():
            assert csv.read_bytes() == (outputs[1] / csv.relative_to(outputs[0])).read_bytes()
    if (outputs[0] / "study.json").exists():
        assert (outputs[0] / "study.json").read_bytes() == (outputs[1] / "study.json").read_bytes()
    before = first[0].read_bytes()
    rejected = run_script(script, cwd=tmp_path, args=[*options, "--output", str(outputs[0])])
    assert rejected.returncode != 0
    assert "Output is not empty" in rejected.stderr
    assert first[0].read_bytes() == before
