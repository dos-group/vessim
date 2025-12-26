from datetime import datetime
import vessim as vs

class CustomController(vs.Controller):
    """A custom controller that monitors multiple microgrids."""
    
    def step(self, time: datetime, microgrid_states: dict[str, dict]) -> None:
        berlin = microgrid_states["Berlin"]
        mumbai = microgrid_states["Mumbai"]

        # Print the power delta (p_delta) for both microgrids
        # p_delta > 0: Microgrid has excess power (needs to charge battery or export)
        # p_delta < 0: Microgrid needs power (needs to discharge battery or import)
        print(f"{time.strftime('%H:%M')}: Berlin: {berlin['p_delta']:.0f}W, Mumbai: {mumbai['p_delta']:.0f}W")


def main():
    environment = vs.Environment(sim_start="2022-06-15", step_size=300)

    # Berlin datacenter
    berlin = environment.add_microgrid(
        name="Berlin",
        actors=[
            vs.Actor(name="server", signal=vs.StaticSignal(value=-800)),
            vs.Actor(name="solar", signal=vs.Trace.load("solcast2022_global", column="Berlin", params={"scale": 2000})),
        ],
        storage=vs.SimpleBattery(capacity=700, initial_soc=0.7),
    )

    # Mumbai datacenter
    mumbai = environment.add_microgrid(
        name="Mumbai",
        actors=[
            vs.Actor(name="server", signal=vs.StaticSignal(value=-700)),
            vs.Actor(name="solar", signal=vs.Trace.load("solcast2022_global", column="Mumbai", params={"scale": 1800})),
        ],
        storage=vs.SimpleBattery(capacity=500),
    )

    # Add monitoring
    monitor = vs.Monitor([berlin, mumbai], outfile="./results.csv")
    environment.add_controller(monitor)

    # Add our custom controller
    load_balancer = CustomController([berlin, mumbai])
    environment.add_controller(load_balancer)

    # Run simulation for 12 hours
    environment.run(until=12 * 3600)

if __name__ == "__main__":
    main()
