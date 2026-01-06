from datetime import datetime
import vessim as vs

def main():
    sim_start = datetime.now()
    environment = vs.Environment(sim_start=sim_start, step_size=10)

    # Software-in-the-Loop examples often require real credentials and running services.
    # This example demonstrates the setup but mocks the signals for runnability.

    # 1. Prometheus Signal (Commented out as it requires a running Prometheus instance)
    # server_signal = vs.PrometheusSignal(
    #     prometheus_url="http://localhost:30826/prometheus",
    #     query="sum(DCGM_FI_DEV_POWER_USAGE)",
    #     username="username",
    #     password="password"
    # )
    # For demonstration, we use a StaticSignal instead:
    server_signal = vs.StaticSignal(value=-500)

    server = vs.Actor(name="gpu", signal=server_signal)

    solar = vs.Actor(name="solar", signal=vs.Trace.load(
        dataset="solcast2022_global",
        column="Berlin",
        params={"scale": 200, "start_time": sim_start} # Scale to 200W
    ))

    battery = vs.SimpleBattery(
        capacity=1000,
        initial_soc=0.6  # Start at 60% charge
    )

    # 2. WattTime Signal (Commented out as it requires API credentials)
    # grid_signal = vs.WatttimeSignal(
    #     username="username",
    #     password="password",
    #     location=(52.5200, 13.4050),
    # )
    # For demonstration, we use None (or a Mock signal if we had one implemented)
    grid_signals = {}

    microgrid = environment.add_microgrid(
        name="gpu_cluster",
        actors=[server, solar],
        storage=battery,
        grid_signals=grid_signals,
    )

    # Expose the microgrid state via REST API and export metrics to Prometheus
    # (Requires 'vessim[sil]' installed)
    try:
        environment.add_controller(vs.Api(export_prometheus=True))
    except ImportError:
        print("Vessim SiL extension not installed. Skipping API controller.")
        print("Install with: pip install vessim[sil]")

    # Run simulation
    # rt_factor=1 runs the simulation in real-time (1 simulation second = 1 real second)
    print("Starting simulation... (Press Ctrl+C to stop)")
    try:
        environment.run(until=3600*24, rt_factor=1)
    except KeyboardInterrupt:
        print("Simulation stopped.")

if __name__ == "__main__":
    main()
