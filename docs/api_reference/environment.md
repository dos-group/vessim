# Environment and RunResult

Create and run simulations with `Environment`.
Its `run()` method returns a `RunResult` containing the final state.
See [Getting Started](../getting_started.md#run-your-first-simulation) for a walkthrough or [Connect External Simulators](../concepts/coupling.md) for Mosaik.

::: vessim.Environment

::: vessim.RunResult

## Time and final state

Actor sampling intervals must be whole multiples of the environment's `step_size`.
Inputs are held between samples.
Controller changes to an actor's input take effect at its next sample, while changes to policy parameters affect the next dispatch.

Ticks occur strictly before `until`.
The final integration interval is shortened as needed to reach that horizon.
`RunResult.states` contains the final resource state, while `last_time` and recorded observations refer to the last tick.
Energy metrics include the final interval.

## Mosaik connections

With `backend="mosaik"`, `env.world` exposes the Mosaik world.
Call `env.prepare()` before connecting to microgrids through `env.entities[name]`, then use `env.run()` to execute and clean up the coupled simulation.

The microgrid input `power` is in W, with generation positive and consumption negative.
Multiple external inputs are summed with local actor power.
A microgrid fed entirely by external simulators may have no actors, but still needs dispatchables to balance its power.

Available outputs are `p_delta`, `p_grid`, `actor_states`, `dispatch_states`, `policy_state`, and `grid_signals`.
Vessim uses integer-second scheduling with Mosaik's `time_resolution=1.0`.
