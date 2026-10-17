"""Optional mosaik adapter. The native execution path never imports this module."""

from __future__ import annotations

import asyncio
import math
import warnings

try:
    import mosaik
    import mosaik_api_v3
except ImportError as exc:
    raise ImportError("The mosaik backend requires: pip install 'vessim[mosaik]'") from exc

from vessim._runtime import Runtime


class MosaikBackend:
    def __init__(self, sim_config: dict):
        self._simulator_name = "Vessim"
        while self._simulator_name in sim_config:
            self._simulator_name += "_"
        self.world = mosaik.World(
            {**sim_config, self._simulator_name: {"python": "vessim._mosaik:VessimSimulator"}},
            skip_greetings=True,
            configure_logging=False,
        )
        self.entities: dict = {}
        self.runtime: Runtime

    def prepare(self, runtime: Runtime) -> None:
        self.runtime = runtime
        sim = self.world.start(self._simulator_name, runtime=runtime)
        for grid in runtime.grids:
            self.entities[grid.name] = sim.Microgrid(name=grid.name)

    def run(self, until: float, live: bool, print_progress) -> None:
        horizon = math.ceil(until) if math.isfinite(until) else until
        # mosaik warns even for microseconds of normal scheduling latency. Our
        # shared runtime reports lateness using the configured threshold.
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="Simulation too slow for real-time factor",
                category=UserWarning,
                module=r"mosaik\.scheduler",
            )
            self.world.run(
                horizon,  # type: ignore[arg-type]
                rt_factor=1.0 if live else None,
                print_progress=print_progress,
                shutdown=False,
            )
        # mosaik handles some exceptions internally. Preserve Vessim's lifecycle
        # and never report a partially executed finite run as successful.
        if self.runtime.error is not None:
            raise self.runtime.error
        if math.isfinite(until):
            expected = math.ceil(until / self.runtime.environment.step_size)
            unfinished = [
                name
                for name, sim in self.world.compile(use_cache=True).items()
                if sim.progress.time.time < horizon
            ]
            if self.runtime.steps != expected or unfinished:
                raise RuntimeError(
                    "mosaik stopped before all simulators completed the requested horizon. "
                    f"Unfinished simulators: {unfinished}"
                )
        else:
            raise KeyboardInterrupt

    def close(self) -> None:
        loop = self.world.loop
        if loop.is_closed():
            return
        # Failed mosaik runs may leave sibling scheduler tasks pending. Cancel
        # them before shutdown so no task outlives the resources it accesses.
        pending = {t for t in asyncio.all_tasks(loop) if t.get_name().startswith("Runner for ")}
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        self.world.shutdown()


class VessimSimulator(mosaik_api_v3.Simulator):
    META = {
        "type": "time-based",
        "models": {
            "Microgrid": {
                "public": True,
                "params": ["name"],
                "attrs": [
                    "power",
                    "p_delta",
                    "p_grid",
                    "actor_states",
                    "dispatch_states",
                    "policy_state",
                    "grid_signals",
                ],
            },
        },
    }

    def __init__(self):
        super().__init__(self.META)
        self.names: set[str] = set()
        self.runtime: Runtime

    def init(self, sid, time_resolution=1.0, **sim_params):
        if time_resolution != 1.0:
            raise ValueError("Vessim requires mosaik time_resolution=1.0 (seconds).")
        self.runtime = sim_params["runtime"]
        return self.meta

    def create(self, num, model, **model_params):
        if num != 1:
            raise ValueError("Create microgrid entities individually with unique names.")
        name = model_params["name"]
        if name in self.names or name not in self.runtime.environment.microgrids:
            raise ValueError(f"Unknown or duplicate microgrid: {name}")
        self.names.add(name)
        return [{"eid": name, "type": model}]

    def step(self, time, inputs, max_advance):
        power = {}
        for grid in self.runtime.grids:
            if not grid.actors and not inputs.get(grid.name, {}).get("power"):
                raise ValueError(f"Microgrid '{grid.name}' requires external power inputs.")
        for name, attributes in inputs.items():
            if set(attributes) - {"power"}:
                raise ValueError("Only the 'power' input is supported on Vessim microgrids.")
            power[name] = sum(attributes.get("power", {}).values())
        self.runtime.step(time, power)
        return time + self.runtime.environment.step_size

    def get_data(self, outputs):
        if any("power" in attrs for attrs in outputs.values()):
            raise ValueError("'power' is an input; use 'p_delta' or 'p_grid' as an output.")
        return {
            name: {attr: self.runtime.states[name][attr] for attr in attrs}
            for name, attrs in outputs.items()
        }
