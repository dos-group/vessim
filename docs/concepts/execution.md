# Execution modes and backends

Vessim supports two workflows: large-scale simulation studies and live experiments.
Both use the same actors, dispatchables, policies, and controllers.

## Simulation studies

`Environment(sim_start=..., step_size=...)` advances as fast as possible.
The default native backend calls the component models directly, without a generic
co-simulation scheduler. Specify a finite `until` horizon. An environment runs
once: build fresh mutable models for each scenario and reuse immutable traces.

```python
trace = vs.Trace.from_csv("input.csv")
solar = trace.select("solar")
load = trace.select("load")

with vs.Environment("2026-01-01", step_size=60) as env:
    env.add_microgrid([
        vs.Actor("solar", solar),
        vs.Actor("load", load, consumer=True),
    ], name="site")
    summary = env.add_controller(vs.Summary("results/summary.json"))
    result = env.run(until=86400)
```

`Summary` uses bounded memory and writes its optional JSON output only when the
run is finalized. For detailed investigations, add `MemoryLogger` or `CsvLogger`.
The final observation is available as `result.states`. It is not a trajectory.

For Monte Carlo sampling and configuration exploration, assign a deterministic
seed to each scenario, load traces once per worker, and parallelize independent
runs. The runnable [study example](https://github.com/dos-group/vessim/blob/main/examples/battery_sizing_study.py)
uses Python's `ProcessPoolExecutor`. For short scenarios, worker startup and data
transfer can outweigh parallelism: measure whole-study throughput, not just
single-step time. Do not share mutable batteries, policies, actors, or controllers
between concurrently executing scenarios.

## Live experiments and digital twins

`Environment.live(step_size=...)` advances alongside wall-clock time. The default
backend is still native. `sim_start` optionally labels tick zero. When omitted it
is captured at `run()`. Signal queries always receive elapsed seconds, even if the
label is historical. Controller initialization happens before the pacing clock starts.

A monotonic clock sets tick deadlines. Slow execution produces a warning after
`behind_threshold` seconds. Ticks are not skipped. A finite live run waits through
its requested horizon, including the interval after its final tick. Omit `until`
to run until interrupted. `KeyboardInterrupt` propagates after resource cleanup.

Live signals can be mixed with traces and ordinary simulated components. They are
rejected in study mode, including live *grid* signals. See [live integration](sil.md)
for Prometheus and the REST API. CSV output flushes after each live tick by default.

A digital twin is a live representation of a real system that can inform or launch
accelerated simulation studies. Vessim shares its models between these workflows.
Automatic live-state branching and an optimization framework are not implemented.

## External simulator coupling

Install `pip install 'vessim[mosaik]'` and choose `backend="mosaik"` on either
constructor. The backend exposes one Vessim simulator with a microgrid entity for
each model. Vessim's internal stepping remains the same as native execution.
Mosaik coordinates the surrounding external simulators.

```python
with vs.Environment("2026-01-01", backend="mosaik", sim_config={
    "External": {"python": "my_simulator:Simulator"},
}) as env:
    source = env.world.start("External").Source()
    env.add_microgrid(actors=[], name="site")
    env.add_controller(vs.Summary())
    env.prepare()
    env.world.connect(source, env.entities["site"], ("watts", "power"))
    result = env.run(until=3600)
```

`prepare()` freezes Vessim's topology and registers its entities. It does not start
controllers or advance time. Normally `run()` calls it automatically. Coupling
requires it explicitly so connections can be made first. `env.world` is available
only on the mosaik backend. Always use `env.run()`, rather than `env.world.run()`.

The supported microgrid input is `power`, in W, with generation positive and
consumption negative. Multiple sources are summed and added to local actor power.
A microgrid with no local actors is permitted only on this backend. Outputs are
`p_delta`, `p_grid`, `actor_states`, `dispatch_states`, `policy_state`, and
`grid_signals`. Other incoming attributes are rejected.

Mosaik also supports `cmd` for separate processes and `connect` for existing
simulators. Configure those in `sim_config` using the
[mosaik scenario API](https://mosaik.readthedocs.io/en/3.6.0/scenario-definition.html).
Feedback cycles through external simulators require appropriate time-shifted
connections and initial values. Vessim remains time-based at integer-second
resolution. It does not support arbitrary event-triggered or same-time iterative
updates to its own microgrids. Coupling between entities inside the single Vessim
simulator is not supported. Implement internal coordination in a controller.

The [coupling example](https://github.com/dos-group/vessim/blob/main/examples/external_simulator_coupling.py)
works in both study and live modes. Mosaik is optional. Importing Vessim and running
native scenarios requires neither mosaik nor its simulator API.

## Tick semantics and ownership

At each tick `t`, Vessim:

1. Samples all due actors, retaining slower actors' previous values and states.
2. Advances dispatchable state with the previous power setpoints for one grid step.
3. Aggregates actor/external power and samples current grid signals.
4. Dispatches new power setpoints and constructs observations when needed.
5. Calls controllers in registration order. Their changes affect subsequent computation.

Actor sampling periods must be positive integer multiples of the environment step.
`until` is exclusive: `until=120` with a 60-second step executes ticks 0 and 60.
Fractional horizons are allowed. Only integer scheduled ticks before the horizon
execute. No extra battery integration occurs at the horizon, preserving earlier
Vessim semantics. The final battery state therefore describes the final tick,
while its new setpoint describes the next interval. Built-in initial setpoints
are zero. Custom nonzero initial setpoints are integrated at tick zero.

Observations are detached from component state. Controllers should treat them as
read-only and change the actual model objects to exert control. `RunResult.states`
is detached from retained logger observations as well. Arbitrary objects returned
by custom `state()` implementations must support copying (and JSON/CSV conversion
if using those outputs). Empty dispatchable state is consistently `{}`.

Use `with Environment(...) as env:` when setup acquires resources. `run()` closes
resources on completion, errors, and interruption, and `close()` is idempotent.
Cleanup attempts all registered resources even if one finalizer fails. A primary
simulation error takes precedence over a cleanup error. Custom signal finalizers
must be idempotent if their signal is shared by multiple actors. Do not mutate
scenario topology or sampling intervals after preparation.
