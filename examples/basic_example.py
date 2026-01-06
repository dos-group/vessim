import vessim as vs

# Create the simulation environment
environment = vs.Environment(sim_start="2022-06-09 00:00:00", step_size=300)  # 5min steps

# Add a single microgrid to the simulation
microgrid = environment.add_microgrid(
    name="datacenter",
    actors=[
        # Server that consumes 700W constantly
        vs.Actor(
            name="server",
            signal=vs.StaticSignal(value=-700),  # negative = consumes power
        ),
        # Solar panel that produces up to 5kW based on the Berlin dataset provided by Solcast
        vs.Actor(
            name="solar_panel",
            signal=vs.Trace.load(
                "solcast2022_global",
                column="Berlin",
                params={"scale": 5000}  # 5kW maximum
            ),
        ),
    ],
    storage=vs.SimpleBattery(
        capacity=1500,      # 1500Wh capacity
        initial_soc=0.8,    # Start 80% charged
        min_soc=0.3         # Never go below 30%
    ),
)

# Add monitoring using the simplified controller API
monitor = vs.Monitor(outfile="./results.csv")
environment.add_controller(monitor)

# Run the simulation for 24 hours
environment.run(until=24 * 3600)
