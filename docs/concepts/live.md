# Live simulation

Test an application against a simulated energy system before connecting it to real equipment.
A job scheduler, for example, can observe solar generation and battery charge, start more work when power is available, and scale back when it is scarce.

`vs.Environment.live()` runs alongside real time.
Your application reads state and sends commands through the REST API while Vessim simulates the response of the energy system.

## Connect an application

Install the live integration:

```console
python -m pip install 'vessim[live]'
```

Start with a datacenter drawing 700 W and solar producing 1000 W.
The surplus charges its battery.
Save this as `live_example.py` and run `python live_example.py`:

```python
import vessim as vs


def main():
    with vs.Environment.live(step_size=1) as env:
        env.add_microgrid(
            name="site",
            actors=[
                vs.Consumer("datacenter", signal=700),
                vs.Producer("solar", signal=1000),
            ],
            dispatchables=[
                vs.SimpleBattery("battery", capacity=1000, initial_soc=0.5),
                vs.GridConnection(),
            ],
        )
        env.add_controller(vs.Api(broker_port=8700))
        env.run()


if __name__ == "__main__":
    main()
```

In another terminal, read the latest observation:

```console
curl http://localhost:8700/microgrids/site
```

The response includes actor power, grid exchange, and battery state of charge.
Now represent the scheduler starting more work by raising datacenter demand to 1200 W:

```console
curl -X PUT 'http://localhost:8700/microgrids/site/actors/datacenter/signal?value=1200'
```

Demand now exceeds solar generation, so the battery starts discharging.
Read the state again to observe the change.
Your application can make the same requests as part of its control loop.
The running API lists available requests at `http://localhost:8700/docs`.

Use Ctrl+C to end the simulation.
See [`vs.Api`](../api_reference/controller.md#vessim.Api) for configuration options.

## Use live measurements

You can also combine real equipment with simulated energy infrastructure.
For example, feed measured server demand into Vessim using [`vs.PrometheusSignal`](../api_reference/signal.md#vessim.PrometheusSignal):

```python
power = vs.PrometheusSignal(
    url="http://localhost:9090",
    query="server_power_watts",
)
datacenter = vs.Consumer("datacenter", signal=power)
```

Use this consumer in your live environment and replace the query with a power metric from your monitoring setup.
For other data sources, implement a [custom live signal](signals.md#live-signals).

The [server-monitoring example](https://github.com/dos-group/vessim/blob/main/examples/live_server_monitoring.py) includes a Prometheus setup and optional Grafana dashboards.
Use `Api(export_prometheus=True)` to expose simulation measurements for monitoring.

## Build a digital twin

Live measurements can keep a digital twin aligned with an operating energy system.
Your application can update demand, battery charge, and other model parameters as conditions change.

To explore possible futures, create separate [simulation studies](studies.md) initialized from the observed state.
For example, start a study from the current battery charge and compare how long it could support demand during a grid outage.
Your application supplies the observed state and forecast inputs to those simulations.

See [controllers](controllers.md) for model updates and [results and metrics](results.md) for recording live experiments.
