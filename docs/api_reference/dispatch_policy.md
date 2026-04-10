# Dispatch Policy

A dispatch policy receives the microgrid's current power delta and allocates it
across [Dispatchables](dispatchable.md), returning the remainder to be exchanged
with the public grid. Subclass `DispatchPolicy` to implement custom strategies.
See the [Dispatchables and Dispatch Policies](../concepts/dispatchables.md) concept
page for usage examples.

::: vessim.DispatchPolicy
::: vessim.DefaultDispatchPolicy
