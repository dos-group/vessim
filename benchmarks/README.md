# Performance and engineering report

## Scope and methodology

Measurements were taken locally on macOS 15.5 ARM64 with Python 3.13.7, NumPy 2.4.4,
pandas 3.0.2, and mosaik 3.6.0. The original reference is commit
`cd417e18dd28c7b5240843a34e0bce3d38ed5c9b`. Its 106 existing tests passed before edits.
The benchmark was added and run against that implementation before replacing the
backend. Recorded artifacts are in the repository's `benchmarks/` directory.

`run.py` measures medians of three runs, separately recording scenario construction
and run time. Imports and CSV parsing are outside the timed run. Controller startup,
execution, and finalization are included. New backend preparation happens inside
run time, whereas the original implementation wired simulators during construction.
All cases retain the same complete MemoryLogger trajectory. The CSV case additionally
writes a full CSV. Each microgrid has two actors and one SimpleBattery. Mixed rates
sample one actor every three grid steps. Feedback changes the dispatch policy each tick.

The default 1,000-step inputs are stored in `benchmarks/input.csv` so numerical
regressions do not depend on platform-specific trigonometric input generation.
The pre-refactor, native, and mosaik trajectory checksums match for all six cases.
They cover every logged tick, including battery states, signals, and feedback outputs.
Additional integration tests exercise external power, delayed feedback, failure
cleanup, actual live pacing, and an independent simulator process.

These are lightweight synthetic scenarios. Results depend on hardware, component
cost, logging, dependencies, and workload. In particular the short CSV measurements
show appreciable filesystem variability. They do not predict speedups for expensive
optimization routines, physical models, or remote I/O.

## Single-run results

| Workload | Steps | Original mosaik | Native | New mosaik | Original / native |
|---|---:|---:|---:|---:|---:|
| static | 1,000 | 0.4741 s | 0.0080 s | 0.0207 s | 59.6× |
| traces | 1,000 | 0.4660 s | 0.0120 s | 0.0251 s | 38.9× |
| csv | 1,000 | 0.6311 s | 0.0284 s | 0.0431 s | 22.2× |
| many_grids | 200 | 1.5521 s | 0.0174 s | 0.0213 s | 89.0× |
| mixed_rates | 1,000 | 0.4143 s | 0.0115 s | 0.0235 s | 36.1× |
| feedback | 1,000 | 0.4990 s | 0.0132 s | 0.0265 s | 37.8× |

Both new backends benefit from shared stepping and removal of per-actor simulator
scheduling. Native execution removes the generic scheduler entirely. The new mosaik
adapter schedules Vessim as one simulator containing the microgrid entities, while
leaving external simulators under mosaik's coordination.

Construction also dropped from approximately 3–8 ms to 0.05–0.10 ms in these cases.
This includes a shift of optional mosaik initialization into run time. Compare total
construction plus execution when studying very short scenarios. The first mosaik
run also pays its import cost, visible in the raw timing samples.

## Whole-study throughput and retained memory

`studies.py` constructs fresh models for 1,000 independent scenarios, each with 288
60-second ticks, one trace actor, one battery, and Summary output. It reuses one
prepared trace and includes scenario construction and cleanup. After an optional
import warm-up, sequential execution took **3.14 s with native** (318 scenarios/s)
and **7.13 s with mosaik** (140 scenarios/s). These are single whole-study measurements,
not medians or parallel speedup claims.

Separate tracemalloc runs compare retained output strategies. Trace loading and
imports are excluded. Values describe traced Python allocations, not process RSS
or total NumPy/native-library memory:

| Native output | 1,000 ticks | 10,000 ticks |
|---|---:|---:|
| Final observation only | 7.7 KB | 7.7 KB |
| Summary metrics | 23.3 KB | 23.3 KB |
| Complete trajectory | 1.62 MB | 15.99 MB |

Summary and default results use bounded memory. Parallel study execution is provided
as an ordinary Python example, with deterministic per-scenario seeds and once-per-worker
trace loading. Tests compare sequential and two-worker results. Short scenarios may
not benefit from multiprocessing because spawn/import and serialization costs dominate.

## Profiling and implemented improvements

The original 1,000-step trace profile made approximately 2.46 million calls, dominated
by asyncio, tiered-time operations, dependency progress, and routing. Profiles of all
six current workloads are summarized in `benchmarks/profiles.json`. These instrumented
times must not be compared directly to the unprofiled timing table. The current
trace profiles make approximately 65,000 calls with native and 198,000 with mosaik.

Implemented improvements:

- A single shared tick for both backends, with no per-actor generic scheduling.
- Lazy optional mosaik imports and model construction without backend allocation.
- One default actor signal lookup per sample, with an extensible `sample()` method.
- Integer-nanosecond trace lookups, eliminating repeated timedelta conversions for
  normal integer simulation times. Column views share read-only arrays without a
  mutable cursor or global cache.
- Detached state observations, using shallow copies for flat immutable scalar state
  and deep copies for arbitrary nested custom state. Profiling first exposed generic
  deepcopy as a new hotspot after scheduler removal. The specialized path preserves
  snapshot isolation while avoiding unnecessary recursive work.
- Native runs without controllers skip intermediate full observations. State methods
  are observational getters, not hooks for advancing physical models.
- Compact Summary counters and final-only persistence. Complete trajectories remain
  opt-in through loggers.
- A persistent buffered CSV writer, mode-appropriate flushing, one union schema for
  heterogeneous microgrids, and no per-run Git subprocess lookup.
- One stoppable polling thread per live signal, validation before Prometheus worker
  startup, bounded HTTP calls, reused API connections, and readiness-based broker startup.
- Explicit error/interruption handling and resource cleanup across both backends.

## Further opportunities

| Priority | Opportunity | Expected benefit | Cost / reason deferred |
|---|---|---|---|
| High for expensive controllers | Profile actual dispatch/optimization workloads | Identify the dominant model cost after scheduler removal | Workload-dependent. No optimization framework is introduced here. |
| Medium | Pre-sample immutable traces onto a study's time grid | Remove binary searches across repeated scenarios | Moderate complexity and additional memory. Must preserve fill semantics and avoid changing live/custom signals. |
| Medium for very large datasets | Memory-map prepared arrays across worker processes | Reduce duplicated input memory and CSV parsing across workers | Moderate portability and lifecycle work. Current example already loads once per worker. |
| Medium for heavy logging | Columnar or batched trajectory export | Reduce flattening, string conversion, and large CSV overhead | Additional dependencies and viewer interoperability. Existing CSV format is retained. |
| Medium | More selective observations for metric-only controllers | Avoid actor/policy snapshots when only grid power is needed | Requires a carefully scoped observation API. Do not turn output preferences into a new execution architecture. |
| Medium for live deployments | Typed, validated broker commands and explicit signal freshness | Prevent invalid remote mutations and distinguish stale measurements | Separate API behavior change. Current numeric actor-signal commands and HTTP lifecycle are tested. |
| Workload-dependent | Larger process batches and bounded submission | Amortize process coordination for millions of tiny runs | Python example uses chunks already. A bespoke experiment scheduler is not justified. |
| Later | Independent scenario construction from live state | Enable digital-twin what-if studies | Explicit state/ownership contract required. General branching and optimization are out of scope. |

The viewer currently consumes full trajectories, not Summary JSON. A study-level
comparison UI and richer live monitoring would be separate product work. Debugging
and replay are supporting capabilities, not the main framing of this refactor.

## Reproducing measurements

From an environment with the repository installed and the mosaik extra available:

```console
python benchmarks/run.py --backend native --output /tmp/native.json --profile /tmp/native.prof
python benchmarks/run.py --backend mosaik --output /tmp/mosaik.json --profile /tmp/mosaik.prof
python benchmarks/studies.py --backend native --runs 1000 --output /tmp/studies-native.json
python benchmarks/studies.py --backend mosaik --runs 1000 --output /tmp/studies-mosaik.json
python benchmarks/profile_workloads.py --output /tmp/profiles.json
python -m pstats /tmp/native.prof
```

Use the benchmark script and input fixture with the original revision and
`--backend legacy` to reproduce its API path. Absolute timings will vary.

## Interface decisions

Scenarios remain Python programs. `run()` now returns a compact RunResult and
`add_controller()` returns its controller. `Summary` makes common studies concise.
For coupling, `prepare()` explicitly freezes topology before connections are made.
The CLI remains focused on viewing results, now also available as `python -m vessim`.
The study and live examples have practical command-line options. There is no second
configuration language, mandatory sweep framework, or optimization API to maintain.

See [execution](../docs/concepts/execution.md) for timing, ownership, and coupling contracts.

### Refactoring decisions

The native backend replaces mosaik as the default so ordinary studies avoid generic
scheduler overhead. Mosaik is installed through an optional extra. Its integration
uses one simulator for all Vessim microgrids, replacing the private per-component
adapters. Connections now target `env.entities[name]` after `env.prepare()`.
Individual actors are no longer mosaik entities.

Environments are single-use and study horizons must be finite. This makes resource
ownership and scenario boundaries explicit. Generated microgrid names are deterministic.
Mutable components cannot be shared between microgrids. Preparation freezes topology.

Actor samples reuse one signal lookup. Custom `state()` overrides still work.
Observations are detached, and empty dispatchable state is consistently `{}`.
Tick order and exclusive horizons preserve the recorded baseline trajectories.

CSV output is buffered for studies and flushed per tick for live experiments.
The first tick defines a shared column schema. Later new columns fail explicitly.
Automatic Git subprocess lookups were removed from logging to reduce setup costs.
Metadata records mode, backend, and run status. Cleanup runs on success, failure,
and interruption without replacing global application log handlers.
