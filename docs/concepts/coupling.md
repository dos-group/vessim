# Connect External Simulators

Vessim can connect domain-specific simulators written in any programming language, including simulators running on other computers, through its Mosaik backend.
[Mosaik](https://mosaik.offis.de/) is a co-simulation framework that coordinates simulation time and exchanges data between models.
Each simulator implements Mosaik's interface so it can participate in a shared simulation.

For example, a datacenter simulator can model job scheduling and server power while Vessim models its electricity supply.
You can reuse that simulator and explore how its workloads interact with batteries, renewable generation, and grid constraints.

## Connect a datacenter model

Install the backend:

```console
python -m pip install 'vessim[mosaik]'
```

The [complete example](https://github.com/dos-group/vessim/blob/main/examples/external_simulator_coupling.py) provides a small datacenter simulator whose demand increases as jobs arrive.
Download it as `external_simulator_coupling.py`.
With that file alongside your script, the connection looks like this:

```python
import vessim as vs

with vs.Environment(
    "2026-01-01",
    step_size=60,
    backend="mosaik",
    sim_config={
        "Datacenter": {"python": "external_simulator_coupling:DatacenterSimulator"},
    },
) as env:
    datacenter = env.world.start("Datacenter").Datacenter()
    env.add_microgrid(name="site", actors=[], dispatchables=[vs.GridConnection()])
    recorder = env.add_controller(vs.Recorder())

    env.prepare()
    env.world.connect(datacenter, env.entities["site"], "power")
    env.run(180)
```

Here, the external simulator supplies the microgrid's demand.
`env.prepare()` makes the microgrid available to Mosaik, and `connect()` links the datacenter's power output to it.
When the environment runs, Mosaik advances both simulators and passes the demand to Vessim at each step.
Inspect the recording as usual with `recorder.to_df()` or [calculate metrics](results.md).

## Connect your own simulator

Wrap your model with the [Mosaik simulator API](https://mosaik.readthedocs.io/en/3.6.0/mosaik-api/), or use an existing Mosaik-compatible simulator.
The example loads a Python class locally.
Mosaik can also start a separate process or connect to a simulator already running on another computer through its [simulator configuration](https://mosaik.readthedocs.io/en/3.6.0/simmanager.html).

You can also send Vessim observations back to another simulator, for example to let a scheduler respond to battery charge.
See Mosaik's [feedback connections](https://mosaik.readthedocs.io/en/3.6.0/scenario-definition.html#how-to-achieve-cyclic-data-flows) and the [Vessim connection reference](../api_reference/environment.md#mosaik-connections) for the interface details.
Use `vs.Environment.live(backend="mosaik", ...)` when the coupled simulation should run in real time.
