# Dispatch policy

A dispatch policy allocates the microgrid's power surplus or deficit across [dispatchables](dispatchable.md).
Each `apply()` call assigns feasible resource setpoints and returns `None`.
The microgrid validates bounds and power balance.

See [Dispatchables and policies](../concepts/dispatchables.md) for examples.

::: vessim.DefaultDispatchPolicy
::: vessim.DispatchPolicy
