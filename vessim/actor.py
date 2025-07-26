from __future__ import annotations

import time
from abc import ABC, abstractmethod
from datetime import datetime
from threading import Timer
from typing import Optional

import mosaik_api_v3  # type: ignore

from vessim.signal import Signal


class Actor:
    """Consumer or producer based on a Signal."""

    def __init__(self, name: str, signal: Signal, step_size: Optional[int] = None) -> None:
        self.name = name
        self.step_size = step_size
        self.signal = signal

    def p(self, now: datetime) -> float:
        """Current power consumption/production."""
        return self.signal.now(at=now)

    def state(self, now: datetime) -> dict:
        """Current state of the actor which is passed to controllers on every step."""
        return {
            "name": self.name,
            "signal": str(self.signal),
            "p": self.p(now),
        }

    def finalize(self) -> None:
        self.signal.finalize()


class SilActor(ABC):
    """Marker base class for Software-in-the-Loop actors.

    The Environment class uses this to sanity check that
    SilActor are only used in real-time simulations.
    """
    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def p(self, now: datetime) -> float:
        """Current power consumption/production."""

    @abstractmethod
    def state(self, now: datetime) -> dict:
        """Current state of the actor which is passed to controllers on every step."""

    def finalize(self) -> None:
        """Finalize the actor, e.g., close connections."""


try:
    import requests
except ImportError:
    pass
else:
    class PrometheusActor(SilActor):
        """Actor that pulls energy usage data from a Prometheus instance."""

        def __init__(
                self,
                name: str,
                prometheus_url: str,
                query: str,
                update_interval: float = 5.0,
                timeout: float = 10.0,
                consumer: bool = True,
                username: Optional[str] = None,
                password: Optional[str] = None,
        ):
            """Initialize the PrometheusActor.

            Args:
                name: Actor name
                prometheus_url: Base URL of the Prometheus server (e.g., 'http://localhost:9090')
                query: PromQL query to fetch energy usage data
                update_interval: Interval in seconds between metric updates
                timeout: Request timeout in seconds
                consumer: If True, negates values (Vessim represents consumption as negative)
                username: Username for HTTP Basic Authentication (optional)
                password: Password for HTTP Basic Authentication (optional)
            """
            super().__init__(name)

            self.prometheus_url = prometheus_url.rstrip("/")
            self.query = query
            self.update_interval = update_interval
            self.timeout = timeout
            self.consumer = consumer
            self.username = username
            self.password = password

            self._last_update: Optional[float] = None
            self._cached_value: float = 0.0
            self._stop_polling = False

            # Set up authentication if provided
            self._auth = None
            if username and password:
                import requests.auth
                self._auth = requests.auth.HTTPBasicAuth(username, password)

            # Validate Prometheus connection
            self._validate_connection()

            # Start background polling
            self._start_background_polling()

        def _validate_connection(self) -> None:
            """Validate that we can connect to the Prometheus server."""
            response = requests.get(
                f"{self.prometheus_url}/api/v1/query",
                params={"query": "up"},
                timeout=self.timeout,
                auth=self._auth
            )
            response.raise_for_status()

        def _fetch_current_value(self) -> float:
            """Fetch the current value from Prometheus."""
            response = requests.get(
                f"{self.prometheus_url}/api/v1/query",
                params={"query": self.query},
                timeout=self.timeout,
                auth=self._auth
            )
            response.raise_for_status()

            data = response.json()
            if data["status"] != "success":
                raise ValueError(f"Prometheus query failed: {data}")

            results = data["data"]["result"]
            if not results:
                raise ValueError(f"No data returned for query: {self.query}")

            # Get the value from the first result
            value = float(results[0]["value"][1])
            return -value if self.consumer else value

        def _start_background_polling(self) -> None:
            """Start background polling in a separate thread."""

            def poll():
                if not self._stop_polling:
                    try:
                        self._cached_value = self._fetch_current_value()
                        self._last_update = time.time()
                    except Exception:
                        pass  # Keep using cached value
                    # Schedule next poll
                    Timer(self.update_interval, poll).start()

            Timer(0, poll).start()  # Start immediately

        def p(self, now: datetime) -> float:
            """Return the current power consumption/production.

            Args:
                now: Current simulation time

            Returns:
                Current power value in watts (negative for consumption, positive for production)
            """
            return self._cached_value

        def state(self, now: datetime) -> dict:
            return {
                "prometheus_url": self.prometheus_url,
                "query": self.query,
                "update_interval": self.update_interval,
                "p": self.p(now),
            }

        def finalize(self) -> None:
            """Stop background polling and clean up resources."""
            self._stop_polling = True


class _ActorSim(mosaik_api_v3.Simulator):
    META = {
        "type": "time-based",
        "models": {
            "Actor": {
                "public": True,
                "params": ["actor"],
                "attrs": ["p", "state"],
            },
        },
    }

    def __init__(self):
        super().__init__(self.META)
        self.eid = None
        self.step_size = None
        self.clock = None
        self.actor = None
        self.p = 0
        self.state = {}

    def init(self, sid, time_resolution=1.0, **sim_params):
        self.step_size = sim_params["step_size"]
        self.clock = sim_params["clock"]
        return self.meta

    def create(self, num, model, **model_params):
        assert num == 1, "Only one instance per simulation is supported"
        self.actor = model_params["actor"]
        self.eid = self.actor.name
        return [{"eid": self.eid, "type": model}]

    def step(self, time, inputs, max_advance):
        assert self.clock is not None
        now = self.clock.to_datetime(time)
        assert self.actor is not None
        self.p = self.actor.p(now)
        self.state = self.actor.state(now)
        assert self.step_size is not None
        return time + self.step_size

    def get_data(self, outputs):
        return {self.eid: {"p": self.p, "state": self.state}}

