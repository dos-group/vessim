# Dispatchables and Dispatch Policies

A **Dispatchable** is a controllable energy resource — a battery, generator, or electrolyzer — whose power setpoint is decided each step by a **Dispatch Policy**. Unlike actors (whose power comes from a signal), a dispatchable's power is allocated by the policy from the microgrid's current power delta.

Each `Dispatchable` reports a **feasible range** `(min_power, max_power)` for the upcoming timestep. Negative values represent discharging/generation; positive values represent charging/consumption.

## Battery models

### SimpleBattery

`SimpleBattery` is an ideal, capacity-based model — fast and easy to parameterize. It is the right default for most simulations:

```python
import vessim as vs

battery = vs.SimpleBattery(
    name="battery",
    capacity=5000,        # Wh — total energy capacity
    initial_soc=0.8,      # 80 % charged at simulation start
    min_soc=0.2,          # never discharge below 20 % SoC
    c_rate=0.5,           # optional: cap charge/discharge rate at 0.5C
)
```

`c_rate` is the maximum charge/discharge rate as a fraction of capacity per hour. A 1 kWh battery with `c_rate=0.5` can charge or discharge at most 500 W. If omitted, the only limit is the available energy.

### ClcBattery

`ClcBattery` implements the C-L-C model for lithium-ion batteries ([Kazhamiaka et al., 2019](https://doi.org/10.1186/s42162-019-0070-6)). It captures realistic degradation of charge/discharge limits as a function of current and is appropriate for high-fidelity studies. The default parameterization models a pack of LGM50 21700 Li-ion cells:

```python
battery = vs.ClcBattery(
    name="battery",
    number_of_cells=100,
    initial_soc=0.5,
    min_soc=0.1,
)
```

!!! note
    `ClcBattery` should not be used with large simulation step sizes. For coarse-grained simulations (15 min or more), prefer `SimpleBattery`.

## Multiple dispatchables

`add_microgrid` accepts a list of dispatchables. The default policy serves them in order, so the first one is used until it is exhausted before the next one is touched:

```python
environment.add_microgrid(
    name="datacenter",
    actors=[...],
    dispatchables=[
        vs.SimpleBattery(name="primary", capacity=10000, initial_soc=0.9),
        vs.SimpleBattery(name="backup",  capacity=5000,  initial_soc=0.5),
    ],
)
```

## Dispatch policies

A `DispatchPolicy` receives the microgrid's power delta and allocates it across dispatchables. It returns the power that needs to be exchanged with the public grid.

### DefaultDispatchPolicy

`DefaultDispatchPolicy` is used when no `policy` argument is given to `add_microgrid`. It supports three modes:

**Grid-connected (default)** — allocate the delta in priority order, exchange the remainder with the grid.

```python
policy = vs.DefaultDispatchPolicy(mode="grid-connected")
```

**Islanded** — fully disconnect the microgrid from the grid. If dispatchables cannot cover a deficit, a `RuntimeError` is raised. Use this to verify a self-sufficient design.

```python
policy = vs.DefaultDispatchPolicy(mode="islanded")
```

**Fixed charge power** — force storage to charge or discharge at a constant rate, balancing the difference with the grid. Useful for scheduled charging strategies; only works in grid-connected mode.

```python
policy = vs.DefaultDispatchPolicy(charge_power=200.0)   # charge at 200 W
policy = vs.DefaultDispatchPolicy(charge_power=-500.0)  # discharge at 500 W
```

## Custom dispatchables

To model hardware that does not fit a battery model, subclass `Dispatchable` and implement four methods:

| Method | Description |
|---|---|
| `feasible_range(duration)` | Return `(min_power, max_power)` achievable for the timestep. |
| `step(duration)` | Advance internal state after `current_power` has been set. |
| `config()` | Return static parameters (logged once to `metadata.yaml`). |
| `state()` | Return dynamic state (logged each step to `timeseries.csv`). |

A diesel generator is stateless and only generates (negative power):

```python
class DieselGenerator(vs.Dispatchable):
    def __init__(self, name: str, max_power_w: float):
        super().__init__(name)
        self.max_power_w = max_power_w

    def feasible_range(self, duration: int) -> tuple[float, float]:
        return (-self.max_power_w, 0.0)  # negative = generation

    def step(self, duration: int) -> None:
        pass  # no internal state

    def config(self) -> dict:
        return {"max_power_w": self.max_power_w}

    def state(self) -> dict:
        return {"current_power": self.current_power}
```

Combined with a battery, the default policy will exhaust the battery first and only call on the generator for the remaining deficit:

```python
environment.add_microgrid(
    name="datacenter",
    actors=[...],
    dispatchables=[
        vs.SimpleBattery(name="battery", capacity=10000, initial_soc=0.9),
        DieselGenerator(name="generator", max_power_w=5000),
    ],
)
```

## Custom dispatch policies

For advanced energy management, subclass `DispatchPolicy` and implement `apply`. The microgrid's grid signals are passed in directly, so the policy can be carbon- or price-aware without extra wiring:

```python
class GreenChargePolicy(vs.DispatchPolicy):
    """Only charge batteries when grid carbon intensity is low."""

    def __init__(self, carbon_threshold: float):
        self.carbon_threshold = carbon_threshold

    def apply(self, p_delta, duration, dispatchables, grid_signals=None):
        remaining = p_delta
        carbon = (grid_signals or {}).get("carbon_intensity")

        for d in dispatchables:
            lo, hi = d.feasible_range(duration)
            if remaining > 0:
                # Excess: only charge if grid is clean
                if carbon is not None and carbon > self.carbon_threshold:
                    d.set_power(0.0, duration)
                    continue
                allocated = min(hi, remaining)
            else:
                # Deficit: always discharge
                allocated = max(lo, remaining)
            d.set_power(allocated, duration)
            remaining -= allocated

        return remaining  # remainder goes to the grid


environment.add_microgrid(
    name="datacenter",
    actors=[...],
    dispatchables=[vs.SimpleBattery(name="battery", capacity=5000, initial_soc=0.8)],
    policy=GreenChargePolicy(carbon_threshold=200),
    grid_signals={"carbon_intensity": vs.Trace.from_csv("datasets/watttime_example.csv")},
)
```
