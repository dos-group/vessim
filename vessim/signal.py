from __future__ import annotations

import time
from abc import ABC, abstractmethod
from datetime import timedelta
from itertools import count
from pathlib import Path
from typing import Any, Optional, Literal

import numpy as np
import pandas as pd


class Signal(ABC):
    """Abstract base class for signals."""

    @abstractmethod
    def at(self, elapsed: Optional[timedelta | float] = None) -> float:
        """Return the signal's value at the given elapsed time since `sim_start`.

        `elapsed` accepts a `timedelta` or `float` interpreted as
        seconds since `sim_start`.
        """

    def finalize(self) -> None:
        """Perform necessary finalization tasks of a signal."""


class StaticSignal(Signal):
    _ids = count(0)

    def __init__(self, value: float) -> None:
        self._v = value

    def __repr__(self):
        """Returns a string representation for the Vessim viewer."""
        return f"StaticSignal({self._v})"

    def set_value(self, value: float) -> None:
        self._v = value

    def at(self, elapsed: Optional[timedelta | float] = None):
        return self._v


class Trace(Signal):
    """Replays a time series indexed by elapsed time since simulation start.

    A `Trace` is queried via `at(elapsed)`; the index *is* the offset. Use
    `offset=` for an additional shift on top (e.g. delay a solar trace so it
    starts at sunrise).

    For data that comes with calendar timestamps (CSVs, `pd.date_range(...)`),
    use `Trace.from_csv` (file path) or `Trace.from_datetime` (in-memory
    `Series`/`DataFrame`) — both rebase the first row to elapsed=0 explicitly.

    Args:
        data: A pandas `Series` or `DataFrame`. The index must be either a
            `TimedeltaIndex` or a numeric index (interpreted as elapsed
            *seconds*). Each column represents one zone of data; the column
            name is the zone name. Between samples, values are interpolated
            using `fill_method` (`ffill` or `bfill`).
        offset: Optional shift in elapsed time. Stacks on top of whatever the
            input index already implies. Defaults to no shift.
        on_overflow: What to do if queried beyond the trace's range.
            Currently only `"raise"` is supported. Defaults to `"raise"`.
        column: Default column to use when `at()` is called without one.
            Defaults to None.
        fill_method: How values between timestamps are computed. Either
            `ffill` (use the most recent past value) or `bfill` (use the next
            future value). Defaults to `ffill`.
    """

    def __init__(
        self,
        data: pd.Series | pd.DataFrame,
        offset: Optional[timedelta] = None,
        on_overflow: Literal["raise"] = "raise",
        column: Optional[str] = None,
        fill_method: Literal["ffill", "bfill"] = "ffill",
        repr_: Optional[str] = None,
    ):
        if on_overflow != "raise":
            raise ValueError(
                f"on_overflow={on_overflow!r} is not yet supported. Only 'raise' is available."
            )

        self._fill_method = fill_method
        self._on_overflow = on_overflow
        self.default_column = column
        self.repr_ = repr_

        if not isinstance(data, (pd.Series, pd.DataFrame)):
            raise ValueError(f"Incompatible type {type(data)} for 'data'.")

        # The index *is* the elapsed offset. Datetime-keyed data must be
        # rebased explicitly via Trace.from_datetime / Trace.from_csv.
        raw_index = data.index
        if isinstance(raw_index, pd.TimedeltaIndex):
            offsets_array = raw_index.to_numpy().astype("timedelta64[ns]")
        elif pd.api.types.is_numeric_dtype(raw_index):
            offsets_array = pd.to_timedelta(raw_index, unit="s").to_numpy().astype(
                "timedelta64[ns]"
            )
        else:
            raise TypeError(
                f"Trace requires a TimedeltaIndex or numeric (seconds) index, "
                f"got {type(raw_index).__name__}. For datetime-indexed data use "
                f"Trace.from_datetime(data) (or Trace.from_csv(path) for CSVs)."
            )

        sorter = np.argsort(offsets_array)
        offsets_ns = offsets_array[sorter]
        if offset is not None:
            offsets_ns = offsets_ns + np.timedelta64(offset)

        self._offsets: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        if isinstance(data, pd.Series):
            values = data.to_numpy(dtype=float, copy=True)[sorter]
            mask = ~np.isnan(values)
            self._offsets[str(data.name)] = (offsets_ns[mask], values[mask])
        else:
            for col in data.columns:
                values = data[col].to_numpy(dtype=float, copy=True)[sorter]
                mask = ~np.isnan(values)
                self._offsets[str(col)] = (offsets_ns[mask], values[mask])

    def __repr__(self):
        """Returns a string representation for the Vessim viewer."""
        return f"Trace({self.repr_ or ''})"

    @classmethod
    def from_datetime(
        cls,
        data: pd.Series | pd.DataFrame,
        offset: Optional[timedelta] = None,
        on_overflow: Literal["raise"] = "raise",
        column: Optional[str] = None,
        fill_method: Literal["ffill", "bfill"] = "ffill",
        repr_: Optional[str] = None,
    ) -> Trace:
        """Build a `Trace` from a datetime-indexed `Series` or `DataFrame`.

        The earliest row is rebased to elapsed=0 and the calendar dates are
        discarded — the trace replays starting at `sim_start` regardless of
        when the source data was originally recorded. All other arguments
        match `Trace`.
        """
        index = pd.to_datetime(data.index)
        relative = data.copy()
        relative.index = index - index.min()
        return cls(
            relative,
            offset=offset,
            on_overflow=on_overflow,
            column=column,
            fill_method=fill_method,
            repr_=repr_,
        )

    @classmethod
    def from_csv(
        cls,
        path: str | Path,
        column: Optional[str] = None,
        scale: float = 1.0,
        offset: Optional[timedelta] = None,
        on_overflow: Literal["raise"] = "raise",
        fill_method: Literal["ffill", "bfill"] = "ffill",
    ) -> Trace:
        """Load a `Trace` from a CSV file.

        The CSV must have a datetime in its first column. Remaining columns
        are interpreted as zones. The earliest row is rebased to elapsed=0
        (see `Trace.from_datetime`). See [Signals and Datasets](../concepts/signals.md)
        for the expected schema and recipes for downloading public datasets.

        Args:
            path: Path to the CSV file.
            column: Default column to use when `at()` is called without one.
            scale: Multiplier applied to all values. Useful for normalized data.
            offset: Optional shift in elapsed time. See `Trace`.
            on_overflow: See `Trace`.
            fill_method: See `Trace`.
        """
        df = pd.read_csv(path, index_col=0)
        if scale != 1.0:
            df = df.astype(float) * scale
        return cls.from_datetime(
            df,
            offset=offset,
            on_overflow=on_overflow,
            column=column,
            fill_method=fill_method,
            repr_=str(path),
        )

    def columns(self) -> list:
        """Returns a list of all available columns."""
        return list(self._offsets.keys())

    def at(
        self,
        elapsed: Optional[timedelta | float] = None,
        column: Optional[str] = None,
    ) -> float:
        """Return the trace's value at the given elapsed time since `sim_start`.

        If `elapsed` falls between sample points, `fill_method` decides how to
        interpolate. If `elapsed` falls outside the trace, a `ValueError` is
        raised (subject to `on_overflow`).

        Args:
            elapsed: Elapsed time since `sim_start`. Either a `timedelta` or a
                number (interpreted as seconds). Required.
            column: Column to query. Required if the trace has more than one.

        Raises:
            ValueError: If `elapsed` is None, before the trace start, after
                the trace end, or refers to an unknown column.
        """
        if elapsed is None:
            raise ValueError("Argument elapsed cannot be None.")
        if not isinstance(elapsed, timedelta):
            elapsed = timedelta(seconds=elapsed)
        if column is None:
            column = self.default_column

        resolved = _get_column_name(self._offsets, column)
        offsets, values = self._offsets[resolved]
        np_at = np.timedelta64(elapsed)

        if self._fill_method == "ffill":
            index = offsets.searchsorted(np_at, side="right") - 1
            if index >= 0:
                return values[index]
            raise ValueError(
                f"Elapsed time {elapsed} is before the start of column '{resolved}' "
                f"(trace covers {_td(offsets[0])} to {_td(offsets[-1])} since sim_start)."
            )
        else:
            index = offsets.searchsorted(np_at, side="left")
            if index < offsets.size:
                return values[index]
            raise ValueError(
                f"Elapsed time {elapsed} is after the end of column '{resolved}' "
                f"(trace covers {_td(offsets[0])} to {_td(offsets[-1])} since sim_start)."
            )


def _get_column_name(data: dict[str, Any], column: Optional[str]) -> str:
    if column is None:
        if len(data) == 1:
            return next(iter(data.keys()))
        raise ValueError("Column needs to be specified.")
    if column in data:
        return column
    raise ValueError(f"Cannot retrieve data for column '{column}'.")


def _td(value: np.timedelta64) -> timedelta:
    """Convert a numpy timedelta64 to a Python timedelta for readable error messages."""
    return pd.Timedelta(value).to_pytimedelta()


class SilSignal(Signal):
    """Base class for Software-in-the-Loop signals with background polling.

    This class provides common functionality for signals that need to periodically
    fetch data from external sources (APIs, databases, etc.) and cache the results.

    Args:
        update_interval: Interval in seconds between data updates
        timeout: Request timeout in seconds for external calls
    """

    def __init__(self, update_interval: float = 5.0, timeout: float = 10.0):
        try:
            from threading import Timer
        except ImportError:
            raise ImportError("SilSignal requires threading support")

        self.Timer = Timer
        self.update_interval = update_interval
        self.timeout = timeout

        self._last_update: Optional[float] = None
        self._cached_value: float = 0.0
        self._stop_polling = False

        # Start background polling
        self._start_background_polling()

    def __repr__(self):
        """Returns a string representation for the Vessim viewer."""
        return f"{self.__class__.__name__}(interval={self.update_interval}s)"

    @abstractmethod
    def _fetch_current_value(self) -> float:
        """Fetch the current value from the external source.

        This method should be implemented by subclasses to define how to
        retrieve data from their specific external source.

        Returns:
            Current value from the external source

        Raises:
            Exception: Any exception that occurs during data fetching
        """

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
                self.Timer(self.update_interval, poll).start()

        self.Timer(0, poll).start()  # Start immediately

    def at(self, elapsed: Optional[timedelta | float] = None) -> float:
        """Return the current cached value.

        Args:
            elapsed: Elapsed time since `sim_start` (ignored for real-time data).

        Returns:
            Current cached value
        """
        return self._cached_value

    def finalize(self) -> None:
        """Stop background polling and clean up resources."""
        self._stop_polling = True


class PrometheusSignal(SilSignal):
    """Signal that pulls energy usage data from a Prometheus instance.

    Args:
        prometheus_url: Base URL of the Prometheus server (e.g., 'http://localhost:9090')
        query: PromQL query to fetch energy usage data
        update_interval: Interval in seconds between metric updates
        timeout: Request timeout in seconds
        username: Username for HTTP Basic Authentication (optional)
        password: Password for HTTP Basic Authentication (optional)
    """

    def __init__(
        self,
        prometheus_url: str,
        query: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        update_interval: float = 10,
        timeout: float = 10,
    ):
        try:
            import requests
            import requests.auth
        except ImportError:
            raise ImportError(
                "PrometheusSignal requires 'requests' package. Install with: pip install requests"
            )

        self.requests = requests
        self.prometheus_url = prometheus_url.rstrip("/")
        self.query = query
        self.username = username
        self.password = password

        # Set up authentication if provided
        self._auth = None
        if username and password:
            self._auth = requests.auth.HTTPBasicAuth(username, password)

        # Initialize parent class (starts background polling)
        super().__init__(update_interval=update_interval, timeout=timeout)

        self._validate_connection()

    def _validate_connection(self) -> None:
        """Validate that we can connect to the Prometheus server."""
        try:
            response = self.requests.get(
                f"{self.prometheus_url}/api/v1/query",
                params={"query": "up"},
                timeout=self.timeout,
                auth=self._auth,
            )
            response.raise_for_status()
        except self.requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"Could not connect to Prometheus at '{self.prometheus_url}'. "
                f"Make sure the Prometheus server is running and accessible."
            ) from None

    def _fetch_current_value(self) -> float:
        """Fetch the current value from Prometheus."""
        response = self.requests.get(
            f"{self.prometheus_url}/api/v1/query",
            params={"query": self.query},
            timeout=self.timeout,
            auth=self._auth,
        )
        response.raise_for_status()

        data = response.json()
        if data["status"] != "success":
            raise ValueError(f"Prometheus query failed: {data}")

        results = data["data"]["result"]
        if not results:
            raise ValueError(f"No data returned for query: {self.query}")

        # Get the value from the first result
        return float(results[0]["value"][1])

    def __repr__(self):
        """Returns a string representation for the Vessim viewer."""
        return f"PrometheusSignal({self.query})"


class WatttimeSignal(SilSignal):
    """Real-time carbon intensity signal from WattTime API.

    This signal fetches real-time marginal carbon intensity data from the WattTime API.
    It requires username and password. If the login fails (e.g., user doesn't exist),
    it will prompt the user to confirm auto-registration and request an email address.

    Args:
        username: WattTime API username
        password: WattTime API password
        region: Grid region (balancing authority) code, e.g., 'CAISO_NORTH'.
            Must be provided if location is not specified.
        location: Tuple of (latitude, longitude) coordinates to automatically determine region.
            Alternative to specifying region directly.
        base_url: Base URL for WattTime API, defaults to 'https://api.watttime.org'
        update_interval: Interval in seconds between API calls (default: 300 seconds as
            WattTime updates every 5 minutes)
        timeout: Request timeout in seconds
    """

    def __init__(
        self,
        username: str,
        password: str,
        region: Optional[str] = None,
        location: Optional[tuple[float, float]] = None,
        base_url: str = "https://api.watttime.org",
        update_interval: float = 300,
        timeout: float = 10,
    ) -> None:
        try:
            import requests
            from requests.auth import HTTPBasicAuth
        except ImportError:
            raise ImportError(
                "WatttimeSignal requires 'requests' package. "
                "Install with: pip install 'vessim[sil]'"
            )

        # Validate that not both region and location are provided
        if region is not None and location is not None:
            raise ValueError("Cannot provide both 'region' and 'location'.")
        elif region is None and location is None:
            raise ValueError("Either 'region' or 'location' must be provided.")

        self._requests = requests
        self._auth = HTTPBasicAuth(username, password)
        self._username = username
        self._password = password
        self._base_url = base_url
        self._token: Optional[str] = None
        self._token_expires: Optional[float] = None

        # Try to get initial token (will auto-register if needed)
        self._get_token()

        # Determine region from coordinates if location is provided
        if location is not None:
            self._region = self._get_region_from_location(location)
        else:
            # region is guaranteed to be not None due to validation above
            assert region is not None
            self._region = region

        # Initialize parent class (starts background polling)
        super().__init__(update_interval=update_interval, timeout=timeout)

    def __repr__(self):
        """Returns a string representation for the Vessim viewer."""
        return f"WatttimeSignal(region={self._region})"

    def _get_token(self) -> str:
        """Obtain or refresh authentication token, auto-registering if needed."""
        current_time = time.time()

        # Check if token is still valid (expires after 30 minutes)
        if self._token and self._token_expires and current_time < self._token_expires:
            return self._token

        # Try to get new token
        login_url = f"{self._base_url}/login"
        try:
            response = self._requests.get(login_url, auth=self._auth)
            response.raise_for_status()

            self._token = response.json()["token"]
            # Token expires in 30 minutes, refresh 5 minutes early
            self._token_expires = current_time + (25 * 60)

            return self._token

        except self._requests.HTTPError as e:
            if e.response.status_code == 403:
                # Login failed, try to register
                self._register_user()
                # Retry login after registration
                response = self._requests.get(login_url, auth=self._auth)
                response.raise_for_status()

                self._token = response.json()["token"]
                self._token_expires = current_time + (25 * 60)

                return self._token
            else:
                # Re-raise other HTTP errors
                raise

    def _register_user(self) -> None:
        """Register a new user account with interactive email prompt."""
        print(f"\nUser '{self._username}' not found in WattTime API.")

        # Ask user for confirmation
        confirm = (
            input("Would you like to register a new WattTime account? (y/n): ").strip().lower()
        )
        if confirm not in ["y", "yes"]:
            raise RuntimeError("Registration cancelled by user")

        # Ask for email address
        email = input("Please enter your email address for registration: ").strip()
        if not email or "@" not in email:
            raise ValueError("Valid email address is required for registration")

        print(f"Registering new WattTime account for '{self._username}'...")

        register_url = f"{self._base_url}/register"

        registration_data = {
            "username": self._username,
            "password": self._password,
            "email": email,
        }

        response = self._requests.post(register_url, json=registration_data)
        response.raise_for_status()

        print("✓ Registration successful!")

    def _get_region_from_location(self, location: tuple[float, float]) -> str:
        """Get region code from latitude/longitude coordinates."""
        region_url = f"{self._base_url}/v3/region-from-loc"
        headers = {"Authorization": f"Bearer {self._get_token()}"}
        params = {
            "latitude": str(location[0]),
            "longitude": str(location[1]),
            "signal_type": "co2_moer",
        }

        response = self._requests.get(region_url, headers=headers, params=params)
        response.raise_for_status()

        data = response.json()
        region = data.get("region")
        if not region:
            raise ValueError(f"No region found for coordinates ({location})")

        print(f"Detected region '{region}' for coordinates ({location})")
        return region

    def _fetch_current_value(self) -> float:
        """Fetch current carbon intensity from WattTime API.

        Returns:
            Current marginal carbon intensity in lbs CO2/MWh

        Raises:
            requests.HTTPError: If API request fails
            KeyError: If expected data is not in API response
        """
        token = self._get_token()

        # Get current carbon intensity
        index_url = f"{self._base_url}/v3/signal-index"
        headers = {"Authorization": f"Bearer {token}"}
        params = {"region": self._region, "signal_type": "co2_moer"}

        response = self._requests.get(
            index_url, headers=headers, params=params, timeout=self.timeout
        )
        response.raise_for_status()

        data = response.json()
        return data["data"][0]["value"]