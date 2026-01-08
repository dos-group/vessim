"""
This example acts as a playground for the "First Steps" tutorial:
https://vessim.readthedocs.io/en/latest/tutorials/1_basic_example/
"""
import vessim as vs

# The Environment manages the simulation time and synchronization between simulators.
# In this example, we start on June 9, 2022, with 5-minute (300s) steps.
environment = vs.Environment(sim_start="2022-06-09 00:00:00", step_size=300)

# You can simulate an arbitrary number of (geo-distributed) Microgrids in parallel.
environment.add_microgrid(
    name="datacenter",
    actors=[
        # Actors represent energy consumers (negative values) or producers (positive values).
        # Here we assume a server with a constant power consumption of 700W.
        vs.Actor(name="server", signal=vs.StaticSignal(value=-700)),

        # Every actor is based on a Signal that provides its power value at any given time.
        # This solar panel uses historical trace data, scaled to a 5kW peak.
        vs.Actor(name="solar_panel", signal=vs.Trace.load(
            "solcast2022_global", column="Berlin", params={"scale": 5000}
        )),
    ],
    # Microgrids can be equipped with Energy Storage.
    # Batteries are (dis)charged based on a configurable Dispatch Policy.
    storage=vs.SimpleBattery(capacity=1500, initial_soc=0.8, min_soc=0.3),
)

# Vessim includes various Controllers to monitor and control your microgrid.
# We use a simple in-memory logger to record the simulation results.
logger = vs.MemoryLogger()
environment.add_controller(logger)

# Run the simulation for 24 hours (24 * 3600 seconds).
environment.run(until=24 * 3600)

# Visualize the results using Vessim's built-in plotting functionality.
vs.plot_result_df(logger.to_df())