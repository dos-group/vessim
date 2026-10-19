# Signals

A `Signal` provides numeric input to actors or contextual data such as electricity prices.
See [Actors and signals](../concepts/signals.md) for usage examples.

::: vessim.StaticSignal
::: vessim.Trace
::: vessim.Signal

## Custom signal lifecycle

The environment calls `start()` before a signal is first sampled and `finalize()` when the environment closes, including after a failure.
Shared signals are started and finalized once per environment.
Replaced signals remain owned until cleanup.

A signal may be read by several components at the same simulation time.
Stateful implementations should handle repeated reads consistently.
Create fresh stateful signals for each run.
Immutable traces can be reused, but live signals must not be shared between environments.

## Live signals

These signals require the `live` extra (`pip install 'vessim[live]'`).
See the [Live simulation](../concepts/live.md) page for setup and usage.

Live signals require `Environment.live()` and poll in the background.
They return zero until the first reading and retain the last value if polling fails.
There is no automatic freshness check.
Custom `_fetch_current_value()` implementations should use bounded request timeouts.

::: vessim.LiveSignal
    options:
      members: [at, start, finalize, _fetch_current_value]
::: vessim.PrometheusSignal
::: vessim.WatttimeSignal
