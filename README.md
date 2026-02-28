<p align="center">
    <img alt="Vessim Logo" src="docs/assets/logo.png" width="250" />
</p>

Vessim is a **co-simulation testbed for carbon-aware systems**. 
It allows you to simulate the interaction of computing systems with local energy systems, including renewable energy sources, energy storage, and the public grid.
Vessim can connect domain-specific simulators for power generation and batteries with real software and hardware.

**Check out the [documentation](https://vessim.readthedocs.io/en/latest/)!**

## What can I do with Vessim?

Vessim helps you to understand and optimize how your (distributed) computing system interacts with (distributed) renewable energy sources and battery storage.

- **Carbon-aware applications**: Develop applications that automatically reduce their energy consumption when the grid is powered by fossil fuels, and increase activity when renewable energy is abundant.
- **Energy system composition**: Experiment with adding solar panels, wind turbines, or batteries to see how they would affect your energy costs and carbon emissions.
- **Plan for outages and extreme events**: Simulate power outages or renewable energy fluctuations to understand risks and test backup strategies.
- **Quality assurance**: Apply Vessim in continuous integrating testing to validate software roll-outs in a controlled environment.

Vessim can run simulations faster than real-time, includes historical datasets for realistic scenarios, and can simulate multiple microgrids in parallel. 
You can test scenarios using historical data or connect real applications and hardware to simulated energy systems.


## Example

The scenario below simulates a microgrid consisting of a simulated computing system in Berlin drawing 2000W, 
a solar power plant (modelled based on a dataset provided by [Solcast](https://solcast.com/)), and a 50 kWh battery storage system. 
The Monitor periodically stores the energy system state in InfluxDB and optionally in a CSV file.

```python
import vessim as vs

environment = vs.Environment(sim_start="2022-06-15", step_size=300)  # 5 minute step size

datacenter = environment.add_microgrid(
        name="datacenter",
        coords=(52.5200, 13.4050),
        actors=[
            vs.Actor(name="server", signal=vs.StaticSignal(value=-2000), tag="load"),
            vs.Actor(
                name="solar_panel_1",
                signal=vs.Trace.load(
                    "solcast2022_global",
                    column="Berlin",
                    params={"scale": 8500},
                ),
                tag="solar",
                coords=(52.5210, 13.4060),
            )
         ],
         storage=vs.SimpleBattery(capacity=50000),
)

monitor = vs.Monitor(
        [datacenter],
        outfile="./results.csv",
        influx_config=influx_config,
        sim_id="sim_run_001",         # Optional: Simulation-ID für Filterung
        write_csv=True,               # CSV optional deaktivieren
    )
environment.add_controller(monitor)

environment.run(until=24 * 3600)  # 24h simulated time
```
### Need Help?

When encountering problems running the example above, check out the ready-to-run simulation grafana_example.py in the [`examples/`](examples/) folder.

### Visualization with Grafana

The Monitor streams simulation data in real-time directly to InfluxDB, which can then be visualized in Grafana.
Actors are grouped by tags (e.g., `solar`, `compute`) for organized monitoring. We provide an example dashboard 
that displays microgrid metrics per microgrid and includes a geographical map view for analyzing multiple distributed sites.

**Setup instructions:**

1. **Additional Dependencies** to enable streaming to InfluxDB:
   ```bash
   pip install influxdb-client
   ```

2. **Start InfluxDB and Grafana** using docker-compose:
   ```bash
   docker-compose up -d
   ```
   Default credentials for both services: username `admin`, password `admin123`

3. **Configure InfluxDB**:
   - Open InfluxDB UI at `http://localhost:8086` and login
   - Navigate to API Tokens and generate an All Access API Token
   - Copy the generated token

4. **Create `.env` file** in your project directory and add created Token to file:
   ```
   INFLUX_TOKEN=<your-generated-token>
   ```

5. **Restart services** to apply the token:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

6. **Open Grafana** at `http://localhost:3001`, login, and select the example dashboard to visualize your microgrids and their location

Check out the [tutorials](https://vessim.readthedocs.io/en/latest/tutorials/1_basic_example/) and [`examples/`](examples/)!


## Installation

You can install the [latest release](https://pypi.org/project/vessim/) of Vessim
via [pip](https://pip.pypa.io/en/stable/quickstart/):

```
pip install vessim
```

If you require software-in-the-loop (SiL) capabilities, you should additionally install the `sil` extension:

```
pip install vessim[sil]
```


## Datasets

Vessim comes with ready-to-user datasets for solar irradiance and average carbon intensity provided by

<p float="left">
  <img src="docs/assets/solcast_logo.png" width="120" />
  <span> and </span>
  <img src="docs/assets/watttime_logo.png" width="120" />
</p>

We're working on documentation on how to include custom datasets for your simulations.


## Publications

If you use Vessim in your research, please cite our paper:

- Philipp Wiesner, Ilja Behnke, Paul Kilian, Marvin Steinke, and Odej Kao. "[Vessim: A Testbed for Carbon-Aware Applications and Systems.](https://dl.acm.org/doi/pdf/10.1145/3727200.3727210)" _ACM SIGENERGY Energy Informatics Review 4 (5)_. 2024.

For details in Vessim's software-in-the-loop simulation methodology, refer to:

- Philipp Wiesner, Marvin Steinke, Henrik Nickel, Yazan Kitana, and Odej Kao. "[Software-in-the-Loop Simulation for Developing and Testing Carbon-Aware Applications.](https://doi.org/10.1002/spe.3275)" _Software: Practice and Experience, 53 (12)_. 2023.

For all related papers, please refer to the [documentation](https://vessim.readthedocs.io/en/latest/publications).
