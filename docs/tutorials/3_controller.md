# Controllers

In Vessim, **Controllers** are the brain of your simulation. 
They allow you to monitor the state of the system, implement custom control logic, or exposing the simulation via APIs to real-world carbon-aware applications.


## How Controllers Work

A `Controller` is a class that is executed at every simulation step. It has access to the state of all microgrids and can modify their components (like storage or actors).

To create a custom controller, you inherit from `Controller` and implement the `step` method.

```python
import vessim as vs

class MyController(vs.Controller):
    def start(self, microgrids):
        """Called once before the simulation starts."""
        self.microgrids = microgrids

    def step(self, now, microgrid_states):
        """Called at every simulation step."""
        # Custom logic goes here
        pass
```

### The `step` Method

The `step` method receives two arguments:

*   `now`: The current simulation time (as a `datetime` object).
*   `microgrid_states`: A dictionary containing the current state of each microgrid.

The `microgrid_states` dictionary has the following structure for each microgrid:

*   `p_delta`: The power difference between production and consumption (negative = deficit, positive = surplus).
*   `p_grid`: The power drawn from (negative) or fed into (positive) the grid.
*   `storage_state`: The state of the storage (e.g., `soc`).
*   `actor_states`: The state of individual actors (e.g., current power consumption).
*   `grid_signals`: Current values of grid signals (e.g., carbon intensity).

## Example: Carbon-Aware Controller

Let's implement a simple controller that adjusts the minimum State of Charge (SoC) of a battery based on the current carbon intensity of the grid. The goal is to reserve more energy in the battery when the grid is "dirty" (high carbon intensity).

```python
class CarbonAwareController(vs.Controller):
    def __init__(self, carbon_threshold: float, high_min_soc: float, low_min_soc: float):
        self.carbon_threshold = carbon_threshold
        self.high_min_soc = high_min_soc
        self.low_min_soc = low_min_soc
        self.microgrids = {}

    def start(self, microgrids):
        # Store references to microgrids to modify them later
        self.microgrids = microgrids

    def step(self, now, microgrid_states):
        for name, state in microgrid_states.items():
            # Get current carbon intensity from grid signals
            # Assuming we added a signal named "carbon_intensity" to the microgrid
            carbon_intensity = state["grid_signals"].get("carbon_intensity")
            
            if carbon_intensity is None:
                continue

            storage = self.microgrids[name].storage
            if storage:
                # Adjust min_soc based on carbon intensity
                if carbon_intensity > self.carbon_threshold:
                    print(f"{now}: High carbon ({carbon_intensity}), raising min_soc to {self.high_min_soc}")
                    storage.min_soc = self.high_min_soc
                else:
                    storage.min_soc = self.low_min_soc
```

To use this controller, you simply add it to your environment:

```python
controller = CarbonAwareController(
    carbon_threshold=200, 
    high_min_soc=0.5, 
    low_min_soc=0.1
)
environment.add_controller(controller)
```

## Logging Controllers

Vessim includes built-in controllers for logging simulation data, so you don't have to write your own.

### MemoryLogger
Stores the simulation results in memory. This is great for analysis after the simulation, as seen in the [First Steps](1_basic_example.md) tutorial.

```python
logger = vs.MemoryLogger()
environment.add_controller(logger)
# ... run simulation ...
df = logger.to_df()
```

### CsvLogger
Writes simulation results directly to a CSV file during the simulation. This is useful for long-running simulations where keeping everything in memory isn't feasible.

```python
csv_logger = vs.CsvLogger("results.csv")
environment.add_controller(csv_logger)
```

### InfluxLogger (and Grafana monitoring)

Streams simulation data to [InfluxDB](https://www.influxdata.com/) for real-time visualization with tools like [Grafana](https://grafana.com/). Unlike Prometheus (which is pull-based and only works for real-time simulations), InfluxDB accepts data with arbitrary timestamps — making it suitable for both real-time and faster-than-real-time simulations.

Actors can be annotated with `tag` and `coords` metadata for grouping and geospatial dashboards:

```python
import vessim as vs

environment = vs.Environment(sim_start="2022-06-15", step_size=300)

environment.add_microgrid(
    name="datacenter",
    coords=(52.5200, 13.4050),
    actors=[
        vs.Actor(name="server", signal=vs.StaticSignal(value=-2000), tag="load"),
        vs.Actor(
            name="solar_panel",
            signal=vs.Trace.load("solcast2022_global", column="Berlin", params={"scale": 8500}),
            tag="solar",
            coords=(52.5210, 13.4060),
        ),
    ],
    storage=vs.SimpleBattery(capacity=50000),
)

influx_config = vs.InfluxConfig(
    url="http://127.0.0.1:8086",
    token="vessim-dev-token",
    org="vessim_org",
    bucket="vessim_bucket",
)
environment.add_controller(vs.InfluxLogger(influx_config=influx_config, sim_id="my_sim"))
```

**Quick start with Docker:**

```bash
pip install vessim[monitor]
docker compose -f examples/grafana/docker-compose.yml up -d
python examples/grafana_example.py
```

Then open Grafana at [http://localhost:3001](http://localhost:3001) (admin / admin123) and select the preconfigured dashboard. See [`examples/grafana_example.py`](https://github.com/dos-group/vessim/blob/main/examples/grafana_example.py) for a full multi-microgrid example.

## Advanced Control: Software-in-the-Loop

For more complex scenarios, you might want to control the simulation from an external program or algorithm running in real-time. Vessim supports this via **Software-in-the-Loop (SiL)** simulation.

The `Api` controller exposes the simulation state via a REST API, allowing external agents to interact with the microgrid.

```python
environment.add_controller(vs.Api())
```

In the next tutorial, we will explore how to set up a SiL simulation and interact with Vessim using the API.