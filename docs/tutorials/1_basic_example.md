# First Steps

This tutorial introduces the core concepts of Vessim by simulating a simple energy system.

## A Basic Simulation

The following code simulates a microgrid with a server, a solar panel, and a battery for 24 hours.

```python
import vessim as vs

environment = vs.Environment(sim_start="2022-06-09 00:00:00", step_size=300) # (1)!

environment.add_microgrid( # (2)!
    name="datacenter",
    actors=[
        vs.Actor(name="server", signal=vs.StaticSignal(value=-700)), # (3)!
        vs.Actor(name="solar_panel", signal=vs.Trace.load(
            "solcast2022_global", column="Berlin", params={"scale": 5000}
        )), # (4)!
    ],
    storage=vs.SimpleBattery(capacity=1500, initial_soc=0.8, min_soc=0.3), # (5)!
)

logger = vs.MemoryLogger()
environment.add_controller(logger)

environment.run(until=24 * 3600) # (6)!

vs.plot_result_df(logger.to_df()) # (7)!
```

1.  **Environment**: Manages the simulation time and synchronization. Here, we start on June 9, 2022, with 5-minute steps.
2.  **Microgrid**: You can simulate an arbitrary number of (geo-distributed) microgrids in parallel.
3.  **Actors**: Represent energy consumers (negative values) or producers (positive values).
4.  **Signals**: Every actor is based on a [Signal](2_signals_and_datasets.md) that provides its power value at any given time. Signals can be static (constant), based on historical time-series data, or real-time data streams from running systems.
5.  **Storage**: An optional battery that acts as an energy buffer. Vessim includes several battery models, from simple to more realistic ones. Batteries are (dis)charged based on a configurable dispatch policy.
6.  **Execution**: Runs the simulation for 24 hours.
7.  **Visualization**: Vessim can log the simulation results in memory or on CSV and includes basic visualization utilities.


The above simulation yields the following results:

<iframe src="../../assets/1_basic_example_plot.html" width="100%" height="620px" style="border: 0;"></iframe>

---

## How it Works

Vessim simulations are built around the interaction of four main building blocks:

### 1. Actors and the Grid

**Actors** are the primary entities in your microgrid. At every simulation step, each actor reports its current power usage or production to the microgrid's internal **Grid**. 

The grid then calculates the **Delta Power** ($\Delta P$), which is simply the sum of all actors' power.

- A **positive delta** means you have excess energy (e.g., the sun is shining).
- A **negative delta** means you have a power deficit (e.g., your servers are consuming more than your solar panels produce).

### 2. Energy Storage and Policy

If your microgrid has **Energy Storage** (like a battery), it can be used to balance the delta power. This behavior is governed by a **Dispatch Policy**.

By default, Vessim uses a policy that tries to balance as much of the delta as possible using the battery:

- If there is a **surplus**, the battery is charged.
- If there is a **deficit**, the battery is discharged.

Any remaining delta that cannot be handled by the battery (because it's full, empty, or lacks power) is exchanged with the **Public Grid**.

### 3. Grid Signals

Microgrids can also receive **Grid Signals**, such as real-time energy prices or carbon intensity. Unlike actors, these signals do not consume or produce power themselves. Instead, they provide environmental context that [Controllers](3_controller.md) can use to make "smart" decisions—for example, deciding to charge the battery only when the carbon intensity is low.
