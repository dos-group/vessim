# Software-in-the-Loop

**Software-in-the-Loop (SiL)** simulation lets Vessim interact with real software and hardware systems while the simulation is running. Use it to:

- **Test real applications** — validate energy-aware schedulers, autoscalers, or routing logic against simulated energy scenarios.
- **Use real data sources** — pull live metrics from sensors, monitoring systems, or APIs into the simulation.
- **Hardware-in-the-Loop** — drive a physical battery testbench from a simulated microgrid.

SiL extras are not installed by default. Enable them with:

```console
pip install vessim[sil]
```

## Architecture

Vessim's SiL has two communication directions:

1. **Real-time data → Vessim:** `SilSignal` (and subclasses like `PrometheusSignal` or `WatttimeSignal`) fetches data from external sources in a background thread and feeds it into the simulation.
2. **Vessim → external world:** the `Api` controller exposes the simulation state via a REST API. External programs can read it and send back control commands.

## Real-time signals

A `SilSignal` polls its data source on a background thread, so the simulation never blocks on a network request.

### PrometheusSignal

Pulls a value from a [Prometheus](https://prometheus.io/) query — typical for using real server metrics as the load of a simulated actor:

```python
import vessim as vs

power_signal = vs.PrometheusSignal(
    prometheus_url="http://localhost:9090",
    query='(1 - avg(rate(node_cpu_seconds_total{mode="idle"}[1m]))) * 1000',
)

server = vs.Actor(name="server", signal=power_signal, consumer=True)
```

### WatttimeSignal

Fetches live grid carbon intensity from the [WattTime API](https://watttime.org/):

```python
carbon = vs.WatttimeSignal(
    username="my_user",
    password="my_password",
    region="CAISO_NORTH",
    update_interval=300,
)
```

### Custom SiL signals

Subclass `SilSignal` and implement `_fetch_current_value`:

```python
class MySensorSignal(vs.SilSignal):
    def _fetch_current_value(self) -> float:
        # response = requests.get("http://192.168.1.50/power")
        # return float(response.text)
        return 42.0
```

## The Api controller

`Api` starts a small FastAPI server that bridges the simulation and the outside world:

```python
environment.add_controller(vs.Api(export_prometheus=True, broker_port=8700))
```

Once the simulation is running, the following endpoints are available at `http://localhost:8700`:

| Method & path | Purpose |
|---|---|
| `GET /` | List of microgrids and their actors. |
| `GET /<microgrid>` | Current state of a microgrid (power flows, battery SoC, …). |
| `PUT /<microgrid>` | Send a control command (e.g. mutate a dispatchable property). |
| `GET /metrics` | Prometheus-format metrics (when `export_prometheus=True`). |

**Read the state:**

```bash
curl http://localhost:8700/datacenter
```

```json
{
  "microgrid": "datacenter",
  "time": "2023-01-01T00:00:00",
  "p_delta": -500.0,
  "p_grid": -500.0,
  "dispatch": { "battery": { "soc": 0.8 } },
  "actors":   { "server":  { "power": -500.0 } }
}
```

**Send a control command:**

```bash
curl -X PUT http://localhost:8700/datacenter \
     -H "Content-Type: application/json" \
     -d '{"dispatchable": {"name": "battery", "property": "min_soc", "value": 0.5}}'
```

When `export_prometheus=True`, the `/metrics` endpoint can be scraped by Prometheus and visualized in Grafana — see [`examples/sil/`](https://github.com/dos-group/vessim/tree/main/examples/sil) for a ready-made compose file.

## Walkthrough: real CPU load → simulated microgrid

This example wires up a real Prometheus + node_exporter stack so that the actual CPU usage of the host drives the simulated server's power draw. The full source is at [`examples/sil_example.py`](https://github.com/dos-group/vessim/blob/main/examples/sil_example.py).

```python
import vessim as vs
from datetime import datetime

def main():
    # 2022 to align with the solar trace, but keep today's hour-of-day
    now = datetime.now()
    environment = vs.Environment(sim_start=now.replace(year=2022), step_size=1)

    # Server load is driven by real host CPU usage scraped via Prometheus
    server = vs.Actor(
        name="server",
        consumer=True,
        signal=vs.PrometheusSignal(
            prometheus_url="http://localhost:9090",
            query='(1 - avg(rate(node_cpu_seconds_total{mode="idle"}[1m]))) * 1000',
        ),
    )

    solar = vs.Actor(
        name="solar",
        signal=vs.Trace.load("solcast2022_global", "Berlin", params={"scale": 2000}),
    )

    battery = vs.SimpleBattery(name="battery", capacity=20, initial_soc=0.5)

    environment.add_microgrid(
        name="your_computer",
        actors=[server, solar],
        dispatchables=[battery],
    )

    environment.add_controller(vs.Api(export_prometheus=True))

    # rt_factor=1.0 → run in real time
    environment.run(rt_factor=1.0)

if __name__ == "__main__":
    main()
```

### Running it

1. Install the SiL extras:
   ```console
   pip install 'vessim[sil]'
   ```
2. Start Prometheus + node_exporter:
   ```console
   docker compose -f examples/sil/docker-compose.yml up -d
   ```
   Wait ~15 s for the first scrapes to land.
3. Run the simulation:
   ```console
   python examples/sil_example.py
   ```
4. Hit the API in another terminal:
   ```console
   curl http://localhost:8700/your_computer
   ```
   Drive your CPU up (e.g. `yes > /dev/null`) and watch the server power follow.
5. Optionally start Grafana to visualize the live `/metrics` endpoint:
   ```console
   docker compose -f examples/sil/docker-compose.grafana.yml up -d
   ```
