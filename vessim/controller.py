from __future__ import annotations

import math
import multiprocessing
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, TYPE_CHECKING


if TYPE_CHECKING:
    from vessim.environment import Environment
    from vessim.microgrid import Microgrid, MicrogridState


def _build_experiment_config(environment: Environment) -> dict:
    """Build the static experiment configuration dict shared by loggers."""
    return {
        "environment": {
            "name": environment.name,
            "sim_start": str(environment.sim_start),
            "step_size": environment.step_size,
            "backend": environment.backend,
            "mode": "live" if environment.is_live else "study",
        },
        "microgrids": {
            mg.name: {
                "actors": [actor.config() for actor in mg.actors],
                "dispatchables": [
                    {"name": d.name, "type": d.__class__.__name__, **d.config()}
                    for d in mg.dispatchables
                ],
                "policy": {
                    "type": mg.policy.__class__.__name__,
                    **mg.policy.state(),
                },
                "grid_signals": (
                    {name: str(signal) for name, signal in mg.grid_signals.items()}
                    if mg.grid_signals
                    else None
                ),
                "coords": mg.coords,
            }
            for mg in environment.microgrids.values()
        },
    }


class Controller(ABC):
    """Abstract base class for all controllers in the simulation.

    Controllers are used to monitor the simulation state and to control the
    behavior of the microgrids. They are executed at every simulation step.
    """

    def start(self, environment: Environment) -> None:
        """Executed before the simulation starts.

        Can be overridden to inspect the simulation topology or perform initialization
        that requires access to the `Environment`.
        """

    @abstractmethod
    def step(self, now: datetime, microgrid_states: dict[str, MicrogridState]) -> None:
        """Performs a simulation step.

        Args:
            now: Current datetime in the simulation.
            microgrid_states: Maps microgrid names to their current state.
        """

    def finalize(self) -> None:
        """Executed after simulation has ended. Can be overridden for clean-up."""


class Api(Controller):
    """REST API interface for microgrid data and control.

    The API controller starts a background process with a FastAPI-based broker
    that exposes endpoints to query the current state of the microgrids and to
    send control commands to them.

    Args:
        export_prometheus: Whether to export metrics to Prometheus. Defaults to False.
        broker_port: The port on which the API broker should run. Defaults to 8700.
        request_timeout: Timeout in seconds for broker readiness and HTTP requests.
    """

    def __init__(
        self,
        export_prometheus: bool = False,
        broker_port: int = 8700,
        request_timeout: float = 5.0,
    ):
        try:
            import requests

            self.requests = requests
        except ImportError:
            raise ImportError(
                "Api requires 'requests' package. Install with: pip install vessim[sil]"
            )

        if not math.isfinite(request_timeout) or request_timeout <= 0:
            raise ValueError("request_timeout must be finite and positive.")
        self.request_timeout = request_timeout
        self._session = self.requests.Session()
        self.broker_port = broker_port
        self.broker_url = f"http://localhost:{broker_port}"
        self.broker_process: Optional[multiprocessing.Process] = None
        self.export_prometheus = export_prometheus
        self.microgrids: dict[str, Microgrid] = {}

    def start(self, environment: Environment) -> None:
        self.microgrids = dict(environment.microgrids)
        self._start_broker()
        for mg_name, mg in self.microgrids.items():
            config = {
                "name": mg_name,
                "actors": [actor.config() for actor in mg.actors],
                "dispatch": [
                    {
                        "name": d.name,
                        "type": d.__class__.__name__,
                        **d.config(),
                    }
                    for d in mg.dispatchables
                ],
                "policy": {
                    "type": mg.policy.__class__.__name__,
                    **mg.policy.state(),
                },
                "coords": mg.coords,
            }
            response = self._session.post(
                f"{self.broker_url}/internal/microgrids/{mg_name}",
                json=config,
                timeout=self.request_timeout,
            )
            response.raise_for_status()
        print(f"Registered {len(self.microgrids)} microgrids with API broker.")

    def _start_broker(self):
        from vessim._broker import run_broker

        self.broker_process = multiprocessing.Process(
            target=run_broker, args=(self.broker_port, self.export_prometheus), daemon=True
        )
        self.broker_process.start()
        deadline = time.monotonic() + self.request_timeout
        while time.monotonic() < deadline:
            if not self.broker_process.is_alive():
                raise RuntimeError("The API broker exited during startup.")
            try:
                response = self._session.get(
                    f"{self.broker_url}/microgrids", timeout=min(0.2, self.request_timeout)
                )
                response.raise_for_status()
                break
            except self.requests.RequestException:
                time.sleep(0.02)
        else:
            raise TimeoutError("The API broker did not become ready before request_timeout.")
        prometheus_str = " (incl. Prometheus exporter)" if self.export_prometheus else ""
        print(f"🌐 API{prometheus_str} available at: {self.broker_url}")

    def step(self, now: datetime, microgrid_states: dict[str, MicrogridState]) -> None:
        """Process commands and push microgrid states to broker."""
        response = self._session.get(
            f"{self.broker_url}/internal/commands", timeout=self.request_timeout
        )
        response.raise_for_status()
        commands = response.json().get("commands", [])
        for cmd in commands:
            if cmd.get("type") == "set_parameter":
                microgrid_name = cmd.get("microgrid")
                if microgrid_name not in self.microgrids:
                    continue

                mg = self.microgrids[microgrid_name]
                target = cmd.get("target")
                prop = cmd.get("property")
                val = cmd.get("value")

                if target == "dispatchable":
                    target_name = cmd.get("target_name")
                    d = next((d for d in mg.dispatchables if d.name == target_name), None)
                    if d:
                        setattr(d, prop, val)
                elif target == "policy":
                    setattr(mg.policy, prop, val)
                elif target == "actor":
                    actor_name = cmd.get("target_name")
                    actor = next((a for a in mg.actors if a.name == actor_name), None)
                    if actor and hasattr(actor.signal, "set_value"):
                        actor.signal.set_value(val)

        for mg_name, mg_state in microgrid_states.items():
            response = self._session.post(
                f"{self.broker_url}/internal/data/{mg_name}",
                json={"microgrid": mg_name, "time": now.isoformat(), **mg_state},
                timeout=self.request_timeout,
            )
            response.raise_for_status()

    def finalize(self) -> None:
        """Clean up resources when simulation ends."""
        if self.broker_process and self.broker_process.is_alive():
            self.broker_process.terminate()
            self.broker_process.join(timeout=2)
            if self.broker_process.is_alive():
                self.broker_process.kill()
                self.broker_process.join(timeout=2)
        self._session.close()

        print("🛑 API broker terminated")
