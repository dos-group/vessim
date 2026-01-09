import time
import signal
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


def test_sil_example():
    pytest.importorskip("fastapi")
    # This script runs with rt_factor=1 (real-time), so it blocks.
    # We start it, wait a bit, and terminate it.
    script_path = os.path.join(EXAMPLES_DIR, "sil_example.py")

    # Use context manager to ensure pipes are closed
    with subprocess.Popen(
        [sys.executable, script_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.dirname(EXAMPLES_DIR),
    ) as process:
        try:
            # Wait a bit to let it initialize
            time.sleep(2)
            if process.poll() is not None:
                # It exited early, check why
                stdout, stderr = process.communicate()
                assert False, (
                    f"SiL example exited early with code {process.returncode}.\n"
                    f"Stderr: {stderr.decode()}"
                )

            # Terminate
            process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()

        except Exception:
            process.kill()
            raise

    # If we got here without assertion error, it started successfully
