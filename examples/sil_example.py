"""This example acts as a playground for the "Software-in-the-Loop" tutorial.

https://vessim.readthedocs.io/en/latest/tutorials/4_sil/
"""
import vessim as vs
from datetime import datetime

def main():
    # 1. Setup Environment
    # We use a real-time factor of 1.0, meaning 1 simulation second = 1 real second.
    environment = vs.Environment(sim_start=datetime.now(), step_size=1)

    # 2. Define Components
    # In a Software-in-the-Loop scenario, you'd typically use real-time signals
    # (like PrometheusSignal) to fetch data from your actual systems.
    server_load = vs.StaticSignal(-1000)
    server = vs.Actor(name="server", signal=server_load)

    # Solar simulation based on historical trace data
    solar = vs.Actor(
        name="solar",
        signal=vs.Trace.load("solcast2022_global", "Berlin", params={"scale": 2000})
    )

    battery = vs.SimpleBattery(capacity=5000, initial_soc=0.5)

    # 3. Create Microgrid
    environment.add_microgrid(
        name="datacenter",
        actors=[server, solar],
        storage=battery
    )

    # 4. Add API Controller
    # This starts a local web server (FastAPI) that exposes the simulation state.
    # External tools can query this API or send control commands.
    # Setting export_prometheus=True also enables a /metrics endpoint.
    environment.add_controller(vs.Api(export_prometheus=True))

    print("Starting simulation...")
    print("API available at http://localhost:8700")
    print("Metrics available at http://localhost:8700/metrics")

    # Run the simulation in real-time.
    # You can now use 'curl' or other tools to interact with the API.
    environment.run(rt_factor=1.0)

if __name__ == "__main__":
    main()
