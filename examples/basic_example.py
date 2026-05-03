"""This example accompanies the "Getting Started" walkthrough.

https://vessim.readthedocs.io/en/latest/getting_started/
"""
import os

import vessim as vs

DATASETS = f"{os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}/datasets"

# The Environment manages simulation time and the synchronization between simulators.
# Here we start on June 9, 2022 and step every 5 minutes (300 s).
environment = vs.Environment(sim_start="2022-06-09 00:00:00", step_size=300)

# A microgrid combines actors (consumers/producers), optional dispatchables (batteries,
# diesel/gas generators, ...), and optional grid signals (electricity price, carbon
# intensity, curtailment, demand response, ...).
# Call add_microgrid() multiple times to simulate geo-distributed sites in parallel.
environment.add_microgrid(
    name="datacenter",
    actors=[
        # Actors represent energy consumers or producers.
        # Vessim convention: consumption is negative (here done by consumer=True), and
        # production is positive.
        vs.Actor(name="server", signal=vs.StaticSignal(value=700), consumer=True),

        # Trace replays a CSV indexed by elapsed time since sim_start. The Solcast
        # data is normalized (0..1); we scale it to a 5 kW peak.
        vs.Actor(
            name="solar_panel",
            signal=vs.Trace.from_csv(
                f"{DATASETS}/solcast_example.csv",
                anchor="2022-06-09 00:00:00",
                column="Berlin",
                scale=5000,
            ),
        ),
    ],
    # Dispatchables are controllable resources. The default DispatchPolicy charges on
    # surplus, discharges on deficit, and exchanges any remainder with the public grid.
    dispatchables=[
        vs.SimpleBattery(name="battery", capacity=1500, initial_soc=0.8, min_soc=0.3)
    ],
    # Grid signals provide contextual information that custom policies and controllers
    # can react to. They are also plotted by the experiment viewer. The trace's calendar
    # year is irrelevant: anchor pins which row maps to elapsed=0, then playback is by
    # elapsed time only.
    grid_signals={
        "carbon_intensity": vs.Trace.from_csv(
            f"{DATASETS}/watttime_example.csv",
            anchor="2023-06-08 00:00:00",
        )
    },
)

# CsvLogger writes metadata.yaml + timeseries.csv to the output directory. View the
# results in your browser with: `vessim view results/basic_example`
environment.add_controller(vs.CsvLogger(outdir="results/basic_example"))

# Run the simulation for 24 hours (24 * 3600 seconds).
environment.run(until=24 * 3600)