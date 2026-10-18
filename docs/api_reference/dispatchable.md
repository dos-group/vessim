# Dispatchables

A [dispatch policy](dispatch_policy.md) assigns power to these resources.
Use the built-in grid and battery models, or subclass `Dispatchable` for a custom resource.
See [Dispatchables and policies](../concepts/dispatchables.md) for examples.

Positive power means absorption or export.
Negative power means supply or import.
Battery observations include `current_power` in W, `charge_level` in Wh, and `soc` between 0 and 1.

::: vessim.GridConnection
    options:
      inherited_members: [set_power]
::: vessim.SimpleBattery
    options:
      inherited_members: [set_power]
::: vessim.ClcBattery
    options:
      inherited_members: [set_power]
::: vessim.Dispatchable
::: vessim.Storage
