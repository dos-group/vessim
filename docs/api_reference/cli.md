# Command-Line Interface

Vessim ships with a small CLI for inspecting experiment results in the browser.

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
