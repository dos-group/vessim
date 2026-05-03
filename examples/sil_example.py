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
import os

import vessim as vs

DATASETS = f"{os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}/datasets"


def main():
    # Live mode: sim_start is captured when run() is called and the simulation
    # advances at 1× wall-clock. Trace data is queried by elapsed time since
    # sim_start, so the solar trace starts replaying from "now".
    environment = vs.Environment.live(step_size=1)

    # Server load driven by actual host CPU usage via Prometheus + node_exporter.
    # The query returns CPU utilization (0.0-1.0), scaled to 0-1000W.
    server = vs.Actor(
        name="server",
        consumer=True,
        signal=vs.PrometheusSignal(
            prometheus_url="http://localhost:9090",
            query='(1 - avg(rate(node_cpu_seconds_total{mode="idle"}[1m]))) * 1000',
        ),
    )

    # Solar simulation based on historical trace data, scaled to 2 kW peak.
    solar = vs.Actor(
        name="solar",
        signal=vs.Trace.from_csv(
            f"{DATASETS}/solcast_example.csv",
            anchor="2022-06-08 00:05:00",
            column="Berlin",
            scale=2000,
        ),
    )

    battery = vs.SimpleBattery(name="battery", capacity=20, initial_soc=0.5)

    environment.add_microgrid(
        name="your_computer",
        actors=[server, solar],
        dispatchables=[battery],
    )

    # The API controller exposes a REST API and a /metrics endpoint for Prometheus.
    environment.add_controller(vs.Api(export_prometheus=True))

    environment.run()
    # You can now use 'curl' or other tools to interact with the API.


if __name__ == "__main__":
    main()
