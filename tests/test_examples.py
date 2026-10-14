import subprocess
import os
import sys
import pytest

EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "examples")


def run_script(script_name):
    script_path = os.path.join(EXAMPLES_DIR, script_name)
    result = subprocess.run(
        [sys.executable, script_path],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(EXAMPLES_DIR),  # Run from project root
    )
    return result


def test_basic_example():
    result = run_script("basic_example.py")
    assert result.returncode == 0, f"Script failed with output:\n{result.stderr}"
    assert "Simulation finished successfully" in result.stderr or result.returncode == 0

    # Cleanup
    if os.path.exists("results.csv"):
        os.remove("results.csv")


def test_battery_sizing_study_is_reproducible_across_workers(tmp_path):
    import json

    for workers in (1, 2):
        subprocess.run(
            [
                sys.executable,
                os.path.join(EXAMPLES_DIR, "battery_sizing_study.py"),
                "--scenarios",
                "4",
                "--workers",
                str(workers),
                "--output",
                str(tmp_path / f"{workers}.json"),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    assert json.loads((tmp_path / "1.json").read_text()) == json.loads(
        (tmp_path / "2.json").read_text()
    )


def test_external_simulator_coupling():
    pytest.importorskip("mosaik")
    result = run_script("external_simulator_coupling.py")
    assert result.returncode == 0, result.stderr
    assert "grid_import_wh" in result.stdout


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
