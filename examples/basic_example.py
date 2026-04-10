"""This example accompanies the "Getting Started" walkthrough.

https://vessim.readthedocs.io/en/latest/getting_started/
"""
import vessim as vs

# The Environment manages simulation time and the synchronization between simulators.
# Here we start on June 9, 2022 and step every 5 minutes (300 s).
environment = vs.Environment(sim_start="2022-06-09 00:00:00", step_size=300)

# A microgrid combines actors (consumers/producers), dispatchables (batteries,
# generators, ...), and optional grid signals (carbon intensity, electricity price, ...).
# You can call add_microgrid() multiple times to simulate geo-distributed sites in parallel.
environment.add_microgrid(
    name="datacenter",
    actors=[
        # Actors represent energy consumers (consumer=True) or producers.
        # Vessim convention: consumption is negative, production is positive.
        vs.Actor(name="server", signal=vs.StaticSignal(value=700), consumer=True),

        # Every actor is backed by a Signal. Trace replays historical time-series data;
        # here we scale the normalized Berlin solar trace to a 5 kW peak.
        vs.Actor(name="solar_panel", signal=vs.Trace.load(
            "solcast2022_global", column="Berlin", params={"scale": 5000}
        )),
    ],
    # Dispatchables are controllable resources. The default DispatchPolicy charges on
    # surplus, discharges on deficit, and exchanges any remainder with the public grid.
    dispatchables=[
        vs.SimpleBattery(name="battery", capacity=1500, initial_soc=0.8, min_soc=0.3)
    ],
    # Grid signals provide contextual information that custom policies and controllers
    # can react to. They are also plotted by the experiment viewer. The watttime trace
    # is from 2023 — we shift it via start_time so it lines up with the 2022 sim window.
    grid_signals={
        "carbon_intensity": vs.Trace.load(
            "watttime2023_caiso-north", params={"start_time": "2022-06-09"}
        ),
    },
)

# CsvLogger writes metadata.yaml + timeseries.csv to the output directory. Open the
# results in your browser with: vessim view results/basic_example
environment.add_controller(vs.CsvLogger(outdir="results/basic_example"))

# Run the simulation for 24 hours (24 * 3600 seconds).
environment.run(until=24 * 3600)
