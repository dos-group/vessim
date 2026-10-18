# Controllers

Controllers let you observe and influence a running simulation.
Use them to record results, connect an application, or adjust how a datacenter operates.
A controller can access every microgrid in its environment.

Register controllers with `env.add_controller()` before running the simulation.
You can combine several, for example to record results while testing a control strategy.

## Recorder

[`vs.Recorder`](../api_reference/recorder.md#vessim.Recorder) collects time series and calculates metrics such as grid imports and exports:

```python
recorder = env.add_controller(vs.Recorder("results/experiment"))
```

See [Results and metrics](results.md) to inspect recordings and add your own calculations.

## Api

[`vs.Api`](../api_reference/controller.md#vessim.Api) lets an external application read simulation state and send commands through a REST API.
For example, a job scheduler can observe available solar power and adjust datacenter demand.

Use it with `vs.Environment.live()` to test the application against a simulation running in real time.
[Live simulation](live.md#connect-an-application) walks through the setup and requests.

## Custom controllers

Subclass [`vs.Controller`](../api_reference/controller.md#vessim.Controller) and implement `step()` to respond to observations.
Vessim calls it after each dispatch.
Changes to model inputs or parameters affect subsequent steps.

### Demand response

Consider a datacenter with a flexible connection agreement.
In this scenario, the grid operator can temporarily lower its import limit with advance notice.
The datacenter responds by pausing flexible workloads until more power is available.

The controller passes the announced limit to a datacenter simulator, whose `set_power_budget()` method adjusts workload concurrency.
Its power consumption feeds a `vs.Consumer` through a [custom signal](signals.md#custom-signals).

```python
class DemandResponse(vs.Controller):
    def __init__(self, datacenter, grid):
        self.datacenter = datacenter
        self.grid = grid

    def step(self, now, states):
        limit = states["site"]["grid_signals"]["next_import_limit"]
        self.datacenter.set_power_budget(limit)
        self.grid.max_import = limit
```

Here, each notice applies to the next simulation step, when both the reduced workload and the new connection limit take effect.
When the limit rises again, the simulator resumes more workloads.
`set_power_budget()` belongs to your datacenter model, so you decide how it responds and which workloads can wait.

A controller changes how the system operates.
The [dispatch policy](dispatchables.md#dispatch-policies) then allocates resource power to serve the resulting demand.
Use a policy to choose battery or generator power, and a controller to adjust workload or coordinate several sites.

The [complete example](https://github.com/dos-group/vessim/blob/main/examples/demand_response.py) connects a simple datacenter model and runs through a temporary restriction.
See the [Controller API](../api_reference/controller.md) for initialization and cleanup hooks.
