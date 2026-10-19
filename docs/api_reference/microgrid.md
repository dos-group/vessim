# Microgrid

Create microgrids through [`Environment.add_microgrid()`](environment.md#vessim.Environment.add_microgrid).
Controllers receive their observations as `MicrogridState` dictionaries.

## Power balance and units

The sum of actor and external simulator power is `p_delta`, the surplus or deficit allocated across dispatchables.
A grid connection must be explicitly configured.
Unmet demand or surplus that cannot be absorbed raises an error.

| Quantity | Positive | Negative |
| --- | --- | --- |
| Actor power and `p_delta` | Generation or surplus | Consumption or deficit |
| Dispatchable power | Absorbing power | Supplying power |
| Grid exchange, `p_grid` | Export | Import |

Power is in W, energy and battery capacity in Wh, and state of charge ranges from 0 to 1.
Multiple microgrids share simulation time but have independent power balances unless explicitly coupled.

::: vessim.Microgrid
::: vessim.MicrogridState
