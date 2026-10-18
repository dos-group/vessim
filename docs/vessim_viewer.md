# Vessim Viewer

Explore simulation studies in your browser, from individual runs to comparisons across configurations and uncertain inputs.

- [Results](viewer/index.html?study=optuna-search#results) compares recorded parameters and metrics in tables and plots.
- [Time series](viewer/index.html?study=getting-started#timeseries) shows power flows and component states.
  Choose runs or configurations to overlay their recordings.

## Explore the examples

| Example | What it shows |
| --- | --- |
| [Getting started](viewer/index.html?study=getting-started#results) | Three days of demand, solar generation, and battery operation |
| [Equipment comparison](viewer/index.html?study=infrastructure-year#results) | Wind, solar, and storage configurations over a year |
| [Optimization](viewer/index.html?study=optuna-search#results) | Cost and emissions trade-offs across 100 equipment configurations |
| [Probabilistic sampling](viewer/index.html?study=dispatch-comparison#results) | Dispatch strategies evaluated across different demand realizations |
| [Multiple microgrids](viewer/index.html?study=multiple-microgrids#results) | Equipment choices across three sites |

## Open and share your results

Open a directory of [recorded runs](concepts/results.md), or export an interactive report for static web hosting:

```console
python -m vessim view results/study
python -m vessim view results/study --export report
```

The local viewer opens at `http://localhost:8710`.
Use `--port` to change the port or `--no-browser` to open it yourself.
Export to an empty directory and serve it over HTTP.
Recipients do not need Vessim installed.
