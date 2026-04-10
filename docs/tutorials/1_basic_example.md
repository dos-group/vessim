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
        vs.Actor(name="server", signal=vs.StaticSignal(value=700), consumer=True), # (3)!
        vs.Actor(name="solar_panel", signal=vs.Trace.load(
            "solcast2022_global", column="Berlin", params={"scale": 5000}
        )), # (4)!
    ],
    dispatchables=[
        vs.SimpleBattery(name="battery", capacity=1500, initial_soc=0.8, min_soc=0.3)
    ], # (5)!
    # (6)!
)

environment.add_controller(vs.CsvLogger("results/basic_example"))  # (7)!

environment.run(until=24 * 3600) # (8)!
```

1.  The **Environment** manages the simulation time and synchronization between simulators. In this example, we start on June 9, 2022, with 5-minute steps.
2.  You can simulate an arbitrary number of (geo-distributed) **Microgrids** in parallel, simply add them to the environment.
3.  **Actors** represent energy consumers or producers. Setting `consumer=True` negates the signal value (Vessim convention: consumption is negative, production is positive). Here we assume a server with a constant power consumption of 700W.<br /><br />
    At each simulation step, Vessim sums up the power values of all actors to determine the microgrid's power delta at the current time.
4.  Every actor is based on a [Signal](2_signals_and_datasets.md) that provides its power value at any given time. Signals can be static (constant), based on historical time-series data (Vessim provides some exemplary datasets but you can of course bring your own), or real-time data from physical systems through, e.g., Prometheus.
5.  Optionally, microgrids can be equipped with **Dispatchables** — controllable energy resources like batteries or generators. Unlike actors, their power output is not determined by a signal but managed by a **Dispatch Policy**.<br /><br />
    The `dispatchables` parameter accepts a list of `Dispatchable`s. Vessim includes two battery models (`SimpleBattery` and `ClcBattery`), but you can implement your own by subclassing `Dispatchable`.<br /><br />
    If you don't specify a `policy`, Vessim uses the `DefaultDispatchPolicy`, which tries to absorb as much of the power delta as possible (charging on surplus, discharging on deficit) and exchanges the rest with the public grid.
6.  Optionally, you can also define **Grid Signals** for your microgrid that provide contextual information about the public grid, e.g., energy prices or carbon intensity. Unlike actors, they do not consume or produce power themselves. We omitted them in this simple example.
7.  `CsvLogger` writes simulation results to a directory. After the run it contains `metadata.yaml` (static configuration) and `timeseries.csv` (power flows and battery state at every step). Open the results in the experiment viewer with:<br /><br />
    ```console
    vessim view results/basic_example
    ```
8.  We run the simulation for 24 hours (24 * 3600 seconds).


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

### 2. Dispatchables and Dispatch Policy

**Dispatchables** are controllable energy resources — anything whose power setpoint you can actively manage, such as batteries, diesel generators, or hydrogen electrolyzers. Each dispatchable reports a **feasible range** of power it can accept for a given timestep (accounting for capacity, state-of-charge, c-rate limits, etc.).

A **Dispatch Policy** decides how to distribute the power delta across dispatchables. Vessim's `DefaultDispatchPolicy` iterates through dispatchables in order and allocates as much of the delta as each can handle:

- If there is an **excess**, dispatchables are charged (positive power).
- If there is a **deficit**, dispatchables are discharged (negative power).

Any remaining delta that dispatchables cannot absorb is exchanged with the public grid. You can implement custom policies (subclassing `DispatchPolicy`) for more advanced strategies, such as only charging when the grid carbon intensity is low.

The `DefaultDispatchPolicy` also supports an `"islanded"` mode where the microgrid is not connected to the public grid — if dispatchables cannot fully balance the delta, an error is raised.

### 3. Grid Signals

Microgrids can also receive **Grid Signals**, that can describe energy prices or carbon intensity at the location of the microgrid.
Unlike actors, these signals do not consume or produce power themselves. 
Instead, they provide environmental context that the **Dispatch Policy** and [Controllers](3_controller.md) can use to make smart decisions, for example, only charging the battery when the carbon intensity is low.
