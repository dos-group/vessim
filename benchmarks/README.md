# Benchmarks

These scripts measure simulation speed, recorder overhead, and viewer indexing.
Run them from a checkout installed with `pip install -e .`.
Install `pip install -e '.[mosaik]'` only when comparing backends.
Write reports under `results/` to keep generated measurements out of the repository.

## Backend workloads

```console
python benchmarks/run.py --backend native --output results/benchmarks/native.json
python benchmarks/run.py --backend mosaik --output results/benchmarks/mosaik.json
```

Six workloads cover static inputs, traces, CSV recording, multiple microgrids, mixed sampling intervals, and controller feedback.
Reports contain median setup and execution times, individual timing samples, peak traced Python memory, and trajectory checksums.
Each workload retains its trajectory in memory with metrics disabled, and the CSV case additionally writes it to disk.
Repeated runs must produce the same checksum.
Imports and trace loading are outside the timed workloads, except for lazy backend initialization on first use.
Memory measurements run separately from timing measurements.

Use `--steps` and `--repeats` to change the workload size.
To profile all six workloads separately:

```console
python benchmarks/run.py --output results/benchmarks/native.json --profile results/benchmarks/profiles
python -m pstats results/benchmarks/profiles/traces.prof
```

The fixed `input.csv` is also used to compare native and Mosaik trajectories in `tests/test_backends.py`.
The tests compare every timestamp and recorded field, allowing floating-point roundoff in numeric values.
Separate behavioral tests check power balance, battery state, sampling, and controller ordering against expected results.
Historical timing reports remain available in Git history.

## Study throughput and memory

```console
python benchmarks/studies.py --runs 1000 --output results/benchmarks/studies-native.json
```

This measures sequential scenarios with a shared trace and metrics-only recording, including model construction and cleanup.
It also compares Python allocation peaks for no recorder, metrics only, and full in-memory trajectories at 1,000 and 10,000 steps.
Use `--backend mosaik` for a backend comparison, or `--runs`, `--steps`, and `--memory-steps` for shorter checks.
Traced allocations are not total process memory.

## Annual workloads and parallel execution

```console
python benchmarks/native_study.py --quiet --output results/benchmarks/annual
```

This uses the infrastructure example's synthetic inputs with three reference configurations.
It measures the cost of observations, built-in metrics, custom metrics, and recording to memory or disk over a simulated year.
It also includes five-minute simulations, profiles, and throughput at different worker counts.
Reports separate input preparation, model setup, and simulation time.
Parallel measurements include process startup and writing experiment records, and check that results agree across worker counts.

For a short throughput check:

```console
python benchmarks/native_study.py --quiet --throughput-only --jobs 6 --workers 1 2 --output results/benchmarks/parallel
```

## Viewer

```console
node viewer/benchmark.mjs 10000
```

This measures indexing synthetic configurations in JavaScript, excluding browser rendering and network requests.
For browser checks with 10,000 recorded summaries, use the existing viewer test fixtures:

```console
npm --prefix viewer ci
npm --prefix viewer run build
python viewer/tests/prepare.py
python -m vessim view results/viewer-release/input/large
```

Both viewer datasets are synthetic fixtures, not simulation results.
Compare timings on the same machine with the same dependencies and workload settings.
Profiling adds overhead, so profile timings should not be compared with ordinary execution times.
