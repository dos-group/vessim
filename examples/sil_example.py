"""Software-in-the-Loop example with real Prometheus metrics.

Uses node_exporter CPU metrics from Prometheus as the server power consumption
signal, demonstrating how vessim connects to real monitoring infrastructure.

1. pip install 'vessim[sil]'
2. docker compose -f examples/sil/docker-compose.yml up -d
3. Wait ~15s for Prometheus to collect initial node_exporter scrapes
4. python examples/sil_example.py
5. API available at http://localhost:8700

Visualization (run in a second terminal):
  - NiceGUI dashboard: pip install 'vessim[dashboard]' && python -m dashboard
  - Grafana: docker compose -f examples/sil/docker-compose.grafana.yml up -d
"""
import vessim as vs
from datetime import datetime


def main():
    # sim_start uses 2022 to align with the solcast2022 solar trace dataset,
    # but preserves the current time-of-day for realistic solar output.
    now = datetime.now()
    environment = vs.Environment(
        sim_start=now.replace(year=2022),
        step_size=1,
    )

    # Server load driven by actual host CPU usage via Prometheus + node_exporter.
    # The query returns CPU utilization (0.0-1.0), scaled to 0-1000W.
    server = vs.Actor(
        name="server",
        signal=vs.PrometheusSignal(
            prometheus_url="http://localhost:9090",
            query='(1 - avg(rate(node_cpu_seconds_total{mode="idle"}[1m]))) * 1000',
            consumer=True,
        ),
    )

    # Solar simulation based on historical trace data
    solar = vs.Actor(
        name="solar",
        signal=vs.Trace.load("solcast2022_global", "Berlin", params={"scale": 2000})
    )

    battery = vs.SimpleBattery(name="battery", capacity=20, initial_soc=0.5)

    environment.add_microgrid(
        name="your_computer",
        actors=[server, solar],
        dispatch=battery,
    )

    # The API controller exposes a REST API and a /metrics endpoint for Prometheus.
    environment.add_controller(vs.Api(export_prometheus=True))

    # Run the simulation in real-time.
    # You can now use 'curl' or other tools to interact with the API.
    environment.run(rt_factor=1.0)

if __name__ == "__main__":
    main()
