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

logger = vs.MemoryLogger() # (6)!
environment.add_controller(logger)

environment.run(until=24 * 3600) # (7)!

vs.plot_result_df(logger.to_df()) # (8)!
```

1.  The **Environment** manages the simulation time and synchronization between simulators. In this example, we start on June 9, 2022, with 5-minute steps.
2.  You can simulate an arbitrary number of (geo-distributed) **Microgrids** in parallel, simply add them to the environment.
3.  **Actors** represent energy consumers (negative values) or producers (positive values). In this case we assume a server with a constant power consumption of 700W. At each simulation step, Vessim sums up the power values of all actors to determine the microgrid's power delta at the current time.
4.  Every actor is based on a [Signal](2_signals_and_datasets.md) that provides its power value at any given time. Signals can be static (constant), based on historical time-series data, or real-time data streams from running systems.
5.  Optionally, microgrids can be equipped with battery **Energy Storage** like a battery. Vessim currently includes two battery models, a simple and a more realistic one, however you can also integrate external simulators like Matlab. Batteries are (dis)charged based on a configurable **Dispatch Policy**, which allows you to, e.g., also charge from the public grid if energy is clean or cheap.
6.  Vessim includes various **Controllers** to monitor and control your microgrid. In this example, we use a simple in-memory logger to record the simulation results.
7.  We run the simulation for 24 hours (24 * 3600 seconds).
8.  Vessim includes basic, built-in plotting functionality to visualize the results.


The above simulation yields the following results:

<iframe src="../../assets/1_basic_example_plot.html" width="100%" height="620px" style="border: 0;"></iframe>

---

## How it Works

Vessim simulations are built around the interaction of four main building blocks:

### 1. Actors and the Grid

**Actors** are the primary entities in your microgrid. At every simulation step, each actor reports its current power usage or production to the microgrid's internal **Grid**. 

The grid then calculates the **Delta Power**, which is simply the sum of all actors' power.

- A **positive delta** means you have excess energy
- A **negative delta** means you have a power deficit

### 2. Energy Storage and Policy

If your microgrid has **Energy Storage** (like a battery), it can be used to balance the delta power. This behavior is governed by a **Dispatch Policy**.

By default, Vessim uses a policy that tries to balance as much of the delta as possible using the battery:

- If there is an **excess**, the battery is charged.
- If there is a **deficit**, the battery is discharged.

Any remaining delta that cannot be handled by the battery is exchanged with the public grid.

### 3. Grid Signals

Microgrids can also receive **Grid Signals**, that can describe energy prices or carbon intensity at the location of the microgrid.
Unlike actors, these signals do not consume or produce power themselves. 
Instead, they provide environmental context that [Controllers](3_controller.md) can use to make "smart" decisions, for example, deciding to charge the battery only when the carbon intensity is low.
