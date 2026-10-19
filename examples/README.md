# Examples

Run these commands from a checkout of Vessim with Python 3.12 or newer.
Create an environment and install the versions used for the published simulations:

```console
python -m venv .venv
source .venv/bin/activate
pip install -e . -r examples/requirements.txt
```

To open the viewer from a source checkout, build its assets once with Node.js 22.12 or newer:

```console
npm --prefix viewer ci
npm --prefix viewer run build
```

## Run an example

Each script runs on its own and saves results under `results/`.
Use `--output PATH` to choose a different directory.
Outputs must be empty so a new run cannot overwrite or mix with an earlier study.
Open any saved run or study with `python -m vessim view PATH`.

| Example | Command | Results |
| --- | --- | --- |
| Getting started | `python examples/basic_example.py` | `results/basic_example` |
| Your own CSV | `python examples/replay_csv.py` | `results/replay_csv` |
| Battery sizing | `python examples/battery_sizing_study.py --workers 4` | `results/battery-sizing` |
| Exploring microgrid configurations | `python examples/infrastructure_study.py` | `results/infrastructure-study` |
| Annual optimization | `python examples/infrastructure_study.py --financial --trials 100 --output results/infrastructure-search` | `results/infrastructure-search` |
| Probabilistic dispatch | `python examples/strategy_comparison.py` | `results/strategy-comparison` |
| Demand response | `python examples/demand_response.py` | `results/demand_response` |
| Custom metrics | `python examples/custom_metrics.py` | `results/custom_metrics` |

CSV replay uses a bundled sample by default.
Pass your own file as its first argument.
Study examples record time series by default, and accept `--no-timeseries` for smaller summary-only outputs.
The custom-metrics example saves summaries only.

Stochastic examples use `--seed 42` by default.
Capacity and policy comparisons reuse the same demand scenarios across configurations.
Optimization runs sequentially from a fresh seeded sampler, with `--trials` specifying the total number of evaluations.
The same commands and dependency versions reproduce the inputs, configurations, and metrics.
Execution timestamps and runtimes will differ.
Synthetic demand, weather, prices, and equipment costs are illustrative model assumptions.

## Rebuild the published examples

```console
python examples/build_gallery.py --output results/gallery
python -m vessim view results/gallery
```

This runs the same commands as the individual examples and produces four studies, including 100 annual optimization trials.
Use `--trials` to change the search size or `--seed` to generate another realization.
No previous results are required.

## Connect an external simulator

```console
pip install -e '.[mosaik]'
python examples/external_simulator_coupling.py
```

The included datacenter simulator runs for three simulated minutes.
Add `--live` to run it at wall-clock speed.

## Use live measurements

```console
pip install -e '.[live]'
docker compose -f examples/live/docker-compose.yml up -d
python examples/live_server_monitoring.py --until 300
```

Allow at least a minute for Prometheus to collect CPU samples before starting Vessim.
The example estimates power from CPU utilization and exposes the simulation at `http://localhost:8700`.
It does not measure electrical power.
On Docker Desktop, node_exporter observes the Linux VM hosting the containers.
Use `--prometheus-url` to connect your own monitoring system instead.

For the optional Grafana dashboard at `http://localhost:3001`:

```console
docker compose -f examples/live/docker-compose.grafana.yml up -d
```

Stop the services when finished:

```console
docker compose -f examples/live/docker-compose.grafana.yml down
docker compose -f examples/live/docker-compose.yml down
```

The monitoring images are pinned to [Prometheus 3.15.0](https://github.com/prometheus/prometheus/releases/tag/v3.15.0), [node_exporter 1.12.1](https://github.com/prometheus/node_exporter/releases/tag/v1.12.1), and [Grafana 13.2.4](https://github.com/grafana/grafana/releases/tag/v13.2.4).
