# Software-in-the-Loop (SiL)

Software-in-the-Loop (SiL) simulation allows you to connect Vessim with real-world software and hardware systems. This enables you to:

*   **Test real applications:** Validate energy-aware applications (e.g., a workload scheduler) against simulated energy scenarios.
*   **Use real data sources:** Incorporate real-time data from sensors or APIs (e.g., live grid carbon intensity) into your simulation.
*   **Hardware-in-the-Loop:** Connect physical hardware (like a battery testbench) to the simulation.

## Architecture

Vessim's SiL architecture consists of two main directions of communication:

1.  **Input (Real-time Data $\to$ Vessim):**
    `SilSignal` and its subclasses (like `PrometheusSignal` or `WatttimeSignal`) fetch data from external sources and feed it into the simulation as it runs.

2.  **Output & Control (Vessim $\to$ External World):**
    The `Api` controller exposes the simulation state via a REST API. External agents can query this API to observe the system and send control commands (e.g., "set battery min SoC to 50%").

## Input: Real-time Signals

Vessim provides `SilSignal`, a special type of signal that polls data from an external source in a background thread. This ensures that the simulation doesn't block while waiting for network requests.

### Prometheus Signal
If your system monitors power consumption using [Prometheus](https://prometheus.io/), you can directly use that data in Vessim.

```python
import vessim as vs

# Signal that fetches power usage from a Prometheus query
# The signal updates every 5 seconds
power_signal = vs.PrometheusSignal(
    prometheus_url="http://localhost:9090",
    query="avg(rate(node_cpu_seconds_total[1m])) * 100",
    update_interval=5.0
)

# Use this signal for an actor
server = vs.Actor(name="server", signal=power_signal)
```

### WattTime Signal
The `WatttimeSignal` fetches real-time grid carbon intensity data from the [WattTime API](https://watttime.org/).

```python
# Signal that fetches live carbon intensity for California
carbon_signal = vs.WatttimeSignal(
    username="my_user",
    password="my_password",
    region="CAISO_NORTH",
    update_interval=300  # WattTime updates every 5 mins
)
```

### Custom SiL Signals
You can create your own signal by subclassing `SilSignal` and implementing the `_fetch_current_value` method.

```python
class MySensorSignal(vs.SilSignal):
    def _fetch_current_value(self) -> float:
        # Code to query your sensor API
        # response = requests.get("http://192.168.1.50/power")
        # return float(response.text)
        return 42.0 # Placeholder
```

## Output & Control: The API Controller

The `Api` controller starts a local web server (using FastAPI) that acts as a bridge between the simulation and external tools.

```python
# Enable the API controller
# export_prometheus=True enables a /metrics endpoint for Prometheus scraping
environment.add_controller(vs.Api(export_prometheus=True, broker_port=8700))
```

### REST API Endpoints

Once the simulation is running, the following endpoints are available at `http://localhost:8700`:

*   **GET /**: List of available microgrids and their actors.
*   **GET /microgrid_name**: Get the current state of a microgrid (power flows, battery SoC, etc.).
*   **PUT /microgrid_name**: Send control commands.

**Example: Reading State**
```bash
curl http://localhost:8700/my_microgrid
```
*Response:*
```json
{
  "microgrid": "my_microgrid",
  "time": "2023-01-01T00:00:00",
  "p_delta": -500.0,
  "p_grid": -500.0,
  "storage": { "soc": 0.8 },
  "actors": { "server": { "power": -500.0 } }
}
```

**Example: Sending Commands**
```bash
curl -X PUT http://localhost:8700/my_microgrid \
     -H "Content-Type: application/json" \
     -d '{"storage": {"min_soc": 0.5}}'
```

### Prometheus Exporter
If `export_prometheus=True` is set, Vessim exposes standard Prometheus metrics at `http://localhost:8700/metrics`. This allows you to monitor the entire simulation using Grafana or other dashboards.

## Comprehensive Example

This example simulates a data center powered by solar energy and a battery. It exposes the system via API so an external script (or you!) can control the battery's minimum charge level.

```python
import vessim as vs
from datetime import datetime

def main():
    # 1. Setup Environment (Real-time factor 1.0 = Real-time speed)
    environment = vs.Environment(sim_start=datetime.now(), step_size=1)

    # 2. Define Components
    # In a real scenario, this could be a PrometheusSignal measuring your actual server
    server_load = vs.StaticSignal(-1000) 
    server = vs.Actor(name="server", signal=server_load)

    # Solar simulation
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

    # 4. Add API Controller with Prometheus export
    environment.add_controller(vs.Api(export_prometheus=True))

    print("Starting simulation...")
    print("API available at http://localhost:8700")
    print("Metrics available at http://localhost:8700/metrics")
    
    # Run indefinitely in real-time
    environment.run(rt_factor=1.0)

if __name__ == "__main__":
    main()
```

### Running the Example

1.  Save the code above as `sil_example.py`.
2.  Install the SiL dependencies: `pip install vessim[sil]`.
3.  Run the script: `python sil_example.py`.
4.  Open `http://localhost:8700` in your browser to see the running API.
5.  Use a tool like `curl` or Postman to change the battery's `min_soc` while the simulation is running and observe how the system behavior changes.

## Next Steps

Congratulations! You've completed the Vessim tutorials.

For more details on specific components, check out the **API Reference** section in the navigation menu.
In case of questions, feel free to reach out via our [GitHub Discussions](https://github.com/dos-group/vessim/discussions).
