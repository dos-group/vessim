# Controllers

Controllers run after dispatch at each simulation step.
They can observe the state of all microgrids and modify their components.
See the [Controllers](../concepts/controllers.md) concept page for usage examples.

::: vessim.Controller

::: vessim.Api

### REST API commands

Install `vessim[live]` to use `Api`.
Its running server exposes interactive endpoint documentation at `http://localhost:8700/docs` with the default port.

API commands are acknowledged when queued.
Changes appear in observations after the command is applied and the affected component is sampled again.
Assigning an actor's `signal` through the API replaces its input with a static signal.

For recording and custom metric APIs, see [Recording and metrics](recorder.md).
