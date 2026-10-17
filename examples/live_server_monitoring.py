"""Monitor a real server alongside simulated solar generation and a battery.

Uses node_exporter CPU metrics from Prometheus as the server power consumption
signal, demonstrating how vessim connects to real monitoring infrastructure.

1. pip install 'vessim[live]'
2. docker compose -f examples/live/docker-compose.yml up -d
3. Wait ~15s for Prometheus to collect initial node_exporter scrapes
4. python examples/live_server_monitoring.py
5. API available at http://localhost:8700

Grafana visualization (run in a second terminal):
  - docker compose -f examples/live/docker-compose.grafana.yml up -d
"""

import argparse
import os

import vessim as vs

DATASETS = f"{os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}/datasets"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prometheus-url", default="http://localhost:9090")
    parser.add_argument("--broker-port", type=int, default=8700)
    parser.add_argument("--until", type=float, help="Optional duration in seconds")
    parser.add_argument("--backend", choices=["native", "mosaik"], default="native")
    args = parser.parse_args()
    # Live mode: sim_start is captured when run() is called and the simulation
    # advances at 1× wall-clock. Trace data is queried by elapsed time since
    # sim_start, so the solar trace starts replaying from "now".
    with vs.Environment.live(step_size=1, backend=args.backend) as environment:

        # Server load driven by actual host CPU usage via Prometheus + node_exporter.
        # The query returns CPU utilization (0.0-1.0), scaled to 0-1000W.
        server = vs.Consumer(
            name="server",
            signal=vs.PrometheusSignal(
                url=args.prometheus_url,
                query='(1 - avg(rate(node_cpu_seconds_total{mode="idle"}[1m]))) * 1000',
            ),
        )

        # Solar simulation based on historical trace data, scaled to 2 kW peak.
        solar = vs.Producer(
            name="solar",
            signal=vs.Trace.from_csv(
                f"{DATASETS}/solar_example.csv",
                column="Berlin",
                scale=2000,
            ),
        )

        battery = vs.SimpleBattery(name="battery", capacity=20, initial_soc=0.5)

        environment.add_microgrid(
            name="your_computer",
            actors=[server, solar],
            dispatchables=[battery, vs.GridConnection()],
        )

        # The API controller exposes a REST API and a /metrics endpoint for Prometheus.
        environment.add_controller(vs.Api(export_prometheus=True, broker_port=args.broker_port))

        # Use curl or other tools to interact with the API while this call runs.
        environment.run(until=args.until)


if __name__ == "__main__":
    main()
