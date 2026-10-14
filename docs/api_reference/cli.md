# Command-Line Interface

Vessim ships with a small CLI for inspecting experiment results in the browser.

## Running scenarios

Scenarios are ordinary Python programs, so Python remains the execution interface:

```console
python examples/basic_example.py
python examples/battery_sizing_study.py --scenarios 1000 --workers 4
python examples/live_server_monitoring.py --until 60 --backend native
```

The live example also accepts `--prometheus-url` and `--broker-port`. The study example accepts `--seed` and `--output`. This keeps configuration and extensibility in Python rather than introducing a second scenario language or runner API.

The viewer CLI is also available through `python -m vessim`, ensuring the selected Python environment is used. `Summary` JSON files are intended for analysis. The viewer expects a full CSV trajectory from `CsvLogger`.

## `vessim view`

Launches the experiment viewer on a results directory written by [`CsvLogger`](controller.md).

```
usage: vessim view [-h] [-p PORT] [--no-browser] directory

positional arguments:
  directory             Path to a results directory

options:
  -p PORT, --port PORT  Port to serve on (default: 8710)
  --no-browser          Do not open the browser automatically
```

### Single-experiment mode

Pass a directory that contains a `metadata.yaml` and `timeseries.csv` directly. The viewer opens that single experiment:

```console
vessim view results/basic_example
```

### Multi-experiment mode

Pass a parent directory that contains several experiment subdirectories. The viewer adds a sidebar from which you can browse runs:

```console
vessim view results/
```
