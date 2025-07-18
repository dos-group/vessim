"""Vessim Software-in-the-Loop (SiL) components.

This module provides real-time simulation capabilities for Vessim.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional
from threading import Timer

import requests

from vessim.actor import SilActor


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
        # Create a dummy signal since PrometheusActor doesn't use it
        from vessim.signal import ConstantSignal
        dummy_signal = ConstantSignal(value=0.0)
        super().__init__(name, dummy_signal)

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

    def finalize(self) -> None:
        """Stop background polling and clean up resources."""
        self._stop_polling = True
