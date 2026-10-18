# Dispatchables and policies

Dispatchables are resources whose power is chosen by a dispatch policy, such as batteries, generators, and grid connections.
Each microgrid can contain any combination of them.
At each step, the policy decides how to use these resources to handle the actors' combined power surplus or deficit.

## Dispatchables

A dispatchable can:

- **Absorb surplus power**, for example a dump load or a mechanism for accounting for curtailed generation.
- **Supply missing power**, for example a diesel or gas generator.
- **Do both**, for example a battery or a grid connection.

Each resource defines its operating constraints.
Batteries have capacity and charge-rate limits, grid connections can limit power and ramp rates, and a generator model may include startup delays or minimum output.

### Batteries

[`vs.SimpleBattery`](../api_reference/dispatchable.md#vessim.SimpleBattery) stores surplus energy and supplies it later.
This creates a 1 kWh battery, initially half full, with a charge and discharge limit of 500 W:

```python
import vessim as vs

battery = vs.SimpleBattery("battery", capacity=1000, initial_soc=0.5, c_rate=0.5)
```

The simple model assumes ideal charging and discharging.
[`vs.ClcBattery`](../api_reference/dispatchable.md#vessim.ClcBattery) adds conversion losses and current-dependent limits for more detailed battery simulations.

### Grid connections

[`vs.GridConnection`](../api_reference/dispatchable.md#vessim.GridConnection) imports power to meet demand and exports surplus.
For example, limit imports to 5 kW and exports to 2 kW:

```python
grid = vs.GridConnection("grid", max_import=5000, max_export=2000)
```

Optional `ramp_up` and `ramp_down` constrain changes in power, measured in W per simulation step.
A [controller](controllers.md) can set `grid.connected = False` to simulate an outage and `True` to reconnect.
Omit the grid connection to model an islanded system.

### Custom dispatchables

Subclass [`vs.Dispatchable`](../api_reference/dispatchable.md#vessim.Dispatchable) to model other resources, such as diesel or gas generators.
A custom resource can also account for curtailed generation as an absorption of surplus power.

This example models a running gas turbine with minimum and maximum output and a ramp limit.
The illustrative turbine supplies between 1 and 5 MW and can change its output by up to 0.5 MW per simulation step:

```python
class GasTurbine(vs.Dispatchable):
    def __init__(self, name, min_output, max_output, ramp_limit):
        super().__init__(name)
        self.min_output = min_output
        self.max_output = max_output
        self.ramp_limit = ramp_limit
        self.output = min_output
        self.current_power = -min_output

    def feasible_range(self, duration):
        lower = max(self.min_output, self.output - self.ramp_limit)
        upper = min(self.max_output, self.output + self.ramp_limit)
        return -upper, -lower  # Generation uses negative dispatchable power.

    def step(self, duration):
        self.output = -self.current_power

    def config(self):
        return {
            "min_output": self.min_output,
            "max_output": self.max_output,
            "ramp_limit": self.ramp_limit,
        }

    def state(self):
        return {"current_power": self.current_power}


turbine = GasTurbine("gas_turbine", min_output=1e6, max_output=5e6, ramp_limit=0.5e6)
dispatchables = [turbine, vs.GridConnection()]
```

`feasible_range()` combines the output and ramp constraints.
`step()` remembers the dispatched output for the next step.
`config()` and `state()` expose model parameters and observations for recording.

The turbine starts at its minimum output and stays running.
If demand falls below what it can supply, the grid exports the excess.
Startup, shutdown, and fuel consumption would require extending the model.

## Dispatch policies

A policy receives the actors' net power, called `p_delta`, and the microgrid's set of dispatchables.
A positive delta is surplus generation, and a negative delta is unmet demand.
The policy assigns power to the resources within their operating constraints.

**After dispatch, the remaining power imbalance must be zero.**
If a surplus or deficit remains, the dispatch is infeasible.
Vessim raises an error and records the run as failed.

### Default policy

[`vs.DefaultDispatchPolicy`](../api_reference/dispatch_policy.md#vessim.DefaultDispatchPolicy) uses resources in list order while respecting their constraints.
For example:

```python
dispatchables = [battery, grid]
```

This uses the battery first and exchanges the remaining power with the grid.
Reversing the order prioritizes grid exchange.
Add a generator or curtailment resource to the list when the system needs those options.

The default policy is used automatically.
To request a fixed battery charging power, pass `policy=vs.DefaultDispatchPolicy(charge_power=200)` to `env.add_microgrid()`.
The policy balances this target using available generation and the other resources.

### Custom policies

Choosing when to charge, generate, import, or export is often the main control problem in an energy system.
Policies can range from a simple priority order to forecast-based optimization or reinforcement learning.
Vessim lets you test your own strategies across demand, weather, and price scenarios through [simulation studies](studies.md), including probabilistic inputs.

For the gas turbine and grid connection above, prioritize the cheaper source.
This policy compares the current electricity price with an assumed turbine cost per kWh, then lets the default policy allocate power in that order:

```python
class CostBasedPolicy(vs.DefaultDispatchPolicy):
    def __init__(self, turbine_cost):
        super().__init__()
        self.turbine_cost = turbine_cost

    def apply(self, p_delta, duration, dispatchables, grid_signals=None):
        grid_price = grid_signals["price"]
        ordered = sorted(
            dispatchables,
            key=lambda resource: (
                grid_price if isinstance(resource, vs.GridConnection)
                else self.turbine_cost
            ),
        )
        super().apply(p_delta, duration, ordered, grid_signals)

    def state(self):
        return {"turbine_cost": self.turbine_cost}
```

Pass `policy=CostBasedPolicy(turbine_cost=0.15)` and `grid_signals={"price": 0.10}` to `env.add_microgrid()`, using EUR/kWh for both.
The grid is preferred at this price.
If the price rises above 0.15, the turbine is preferred.
Use a price trace to vary it during the run.

The turbine's minimum output and ramp limits still apply, so the grid supplies any remaining demand or receives excess generation.
This policy covers a turbine and a grid connection.
To add other resource types, define their costs or priority in the ordering rule.

For a different allocation algorithm, implement [`vs.DispatchPolicy.apply()`](../api_reference/dispatch_policy.md#vessim.DispatchPolicy.apply) and assign resource power through `set_power()`, ensuring the final balance is zero.

The [strategy comparison example](https://github.com/dos-group/vessim/blob/main/examples/strategy_comparison.py) compares self-consumption, peak-shaving, and carbon-aware policies.
