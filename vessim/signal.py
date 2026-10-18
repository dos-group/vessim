from __future__ import annotations

import math
import time
from copy import copy
from threading import Event, Thread, current_thread
from abc import ABC, abstractmethod
from datetime import timedelta
from pathlib import Path
from typing import Any, Optional, Literal

import numpy as np
import pandas as pd

from vessim._util import require_finite


class Signal(ABC):
    """A numeric simulation input sampled at elapsed time.

    Use for actor power or contextual data such as prices and carbon intensity.
    The environment calls start() before sampling and finalize() during cleanup.
    """

    def start(self) -> None:
        """Acquire resources before the first simulation sample."""

    @abstractmethod
    def at(self, elapsed: Optional[timedelta | float] = None) -> float:
        """Return the signal's value at the given elapsed time since `sim_start`.

        `elapsed` accepts a `timedelta` or `float` interpreted as
        seconds since `sim_start`.
        """

    def finalize(self) -> None:
        """Perform necessary finalization tasks of a signal."""


class StaticSignal(Signal):
    """A constant numeric input, also used for numeric actor input shorthand.

    Args:
        value: A finite number. Units are determined by the input using it.
    """

    def __init__(self, value: float) -> None:
        self.set_value(value)

    def __repr__(self) -> str:
        """Describe the constant input in experiment configuration."""
        return f"StaticSignal({self._value})"

    def set_value(self, value: float) -> None:
        """Change the value returned by subsequent samples."""
        require_finite(value, "StaticSignal value")
        self._value = value

    def at(self, elapsed: Optional[timedelta | float] = None) -> float:
        """Return the current value, independent of elapsed time."""
        return self._value


class Trace(Signal):
    """Replays a time series indexed by an *offset* since simulation start.

    Internally a `Trace` is always offset-indexed: row 0 sits at offset=0
    seconds, every other row is a positive offset from there. For a `Trace`,
    the queried `elapsed` time and a row's `offset` are the same coordinate:
    `at(elapsed)` returns the value whose offset best matches the elapsed
    time the simulation has accumulated since `sim_start`.

    The accepted index types are:

    - `TimedeltaIndex` or numeric (interpreted as offset *seconds*): used
      as-is. Must start at offset=0. `anchor` must not be provided. This is
      the canonical form.
    - `DatetimeIndex`: a convenience for calendar-stamped data. `anchor` is
      required and must match an existing row exactly. That row is rebased
      to offset=0 and earlier rows are dropped.

    For loading offset-indexed or datetime-indexed CSVs, use `Trace.from_csv`.

    Args:
        data: A pandas `Series` or `DataFrame`. See above for accepted index
            types. Each column represents one zone of data. The column name
            is the zone name. Between samples, values are interpolated using
            `fill_method` (`ffill` or `bfill`). Values must be finite and
            timestamps unique. Handle missing data explicitly before loading.
        anchor: Required when `data` has a `DatetimeIndex`. Must be a value
            present in the index. The matching row is rebased to offset=0.
            Forbidden for `TimedeltaIndex` and numeric indices (which are
            already offset-indexed).
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
        anchor: Optional[pd.Timestamp | str] = None,
        on_overflow: Literal["raise"] = "raise",
        column: Optional[str] = None,
        fill_method: Literal["ffill", "bfill"] = "ffill",
        repr_: Optional[str] = None,
    ):
        if on_overflow != "raise":
            raise ValueError(
                f"on_overflow={on_overflow!r} is not yet supported. Only 'raise' is available."
            )

        if fill_method not in ("ffill", "bfill"):
            raise ValueError("fill_method must be 'ffill' or 'bfill'.")
        self._fill_method = fill_method
        self._on_overflow = on_overflow
        self.default_column = column
        self.repr_ = repr_

        if not isinstance(data, (pd.Series, pd.DataFrame)):
            raise ValueError(f"Incompatible type {type(data)} for 'data'.")

        raw_index = data.index
        if raw_index.hasnans:
            raise ValueError("Trace timestamps must not contain missing values (NaN or NaT).")
        if raw_index.has_duplicates:
            raise ValueError("Trace timestamps must be unique; resolve duplicate rows first.")
        if isinstance(raw_index, pd.DatetimeIndex):
            if anchor is None:
                raise ValueError(
                    "anchor is required for datetime-indexed data. "
                    "Pass anchor=<timestamp> matching a row in your data."
                )
            anchor_ts = pd.to_datetime(anchor)
            if anchor_ts not in raw_index:
                raise ValueError(
                    f"anchor={anchor_ts!s} is not present in the data's index. "
                    f"anchor must match an existing row exactly."
                )
            data = data.loc[raw_index >= anchor_ts]
            assert isinstance(data.index, pd.DatetimeIndex)
            offsets_array = (data.index - anchor_ts).to_numpy().astype("timedelta64[ns]")
        elif isinstance(raw_index, pd.TimedeltaIndex):
            if anchor is not None:
                raise ValueError("anchor is only valid for datetime-indexed data.")
            offsets_array = raw_index.to_numpy().astype("timedelta64[ns]")
        elif pd.api.types.is_numeric_dtype(raw_index):
            if anchor is not None:
                raise ValueError("anchor is only valid for datetime-indexed data.")
            if not np.isfinite(raw_index.to_numpy()).all():
                raise ValueError("Trace offsets must be finite numbers of seconds.")
            offsets_array = (
                pd.to_timedelta(raw_index, unit="s").to_numpy().astype("timedelta64[ns]")
            )
        else:
            raise TypeError(
                f"Trace requires a DatetimeIndex (with anchor=), TimedeltaIndex, "
                f"or numeric (seconds) index, got {type(raw_index).__name__}."
            )

        if offsets_array.size == 0:
            raise ValueError("Trace data cannot be empty.")
        if np.isnat(offsets_array).any():
            raise ValueError("Trace timestamps must be valid and within the supported range.")

        sorter = np.argsort(offsets_array)
        offsets_ns = offsets_array[sorter]
        if np.any(offsets_ns[1:] == offsets_ns[:-1]):
            raise ValueError("Trace timestamps must be unique at nanosecond resolution.")

        if offsets_ns[0] != np.timedelta64(0, "ns"):
            raise ValueError(
                f"Trace must start at offset=0, but starts at {_td(offsets_ns[0])}. "
                f"To delay a trace, pad the beginning of your data with zeros."
            )

        self._offsets: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        columns = [(data.name, data)] if isinstance(data, pd.Series) else list(data.items())
        if not columns:
            raise ValueError("Trace needs at least one value column.")
        for col, series in columns:
            name = str(col)
            if name in self._offsets:
                raise ValueError(f"Trace column names must be unique; duplicate {name!r}.")
            try:
                values = series.to_numpy(dtype=float, copy=True)[sorter]
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Trace column {name!r} must contain numeric values.") from exc
            invalid = np.flatnonzero(~np.isfinite(values))
            if invalid.size:
                raise ValueError(
                    f"Trace column {name!r} has a missing or nonfinite value at "
                    f"offset {_td(offsets_ns[invalid[0]])}. "
                    "Fill or remove missing values explicitly before creating a Trace."
                )
            self._offsets[name] = (offsets_ns, values)

        if column is not None:
            _get_column_name(self._offsets, column)

        for name, (offsets, values) in self._offsets.items():
            offsets = offsets.view("i8")
            offsets.setflags(write=False)
            values.setflags(write=False)
            self._offsets[name] = (offsets, values)
        offsets = offsets_ns.view("i8")
        spacing = np.diff(offsets)
        self._regular_step = (
            int(spacing[0]) if spacing.size and np.all(spacing == spacing[0]) else None
        )

    def select(self, column: str) -> Trace:
        """Return a column view sharing immutable arrays with this trace.

        Load a multi-column CSV once and use views for different actors or
        scenarios. Sampling is stateless. No per-run cursor is stored here.
        """
        _get_column_name(self._offsets, column)
        selected = copy(self)
        selected.default_column = column
        return selected

    def __repr__(self):
        """Returns a string representation for the Vessim viewer."""
        return f"Trace({self.repr_ or ''})"

    @classmethod
    def from_csv(
        cls,
        path: str | Path,
        anchor: Optional[pd.Timestamp | str] = None,
        column: Optional[str] = None,
        scale: float = 1.0,
        on_overflow: Literal["raise"] = "raise",
        fill_method: Literal["ffill", "bfill"] = "ffill",
    ) -> Trace:
        """Load a `Trace` from a CSV file.

        Vessim expects **offset-indexed** CSVs: the first column is the offset
        in seconds since the trace start (row 0 at `0`). Remaining columns are
        value columns (zones, regions, etc.).

        As a utility, datetime-indexed CSVs are also accepted and converted on
        load: pass `anchor=<timestamp>` to mark which row corresponds to
        offset=0. See [Actors and signals](../concepts/signals.md#trace-signals)
        for pandas and CSV examples.

        Args:
            path: Path to the CSV file.
            anchor: Required if the first column is a datetime. Must match a
                row in the data exactly. That row becomes `offset=0` and
                earlier rows are dropped. Forbidden if the first column is
                already numeric.
            column: Default column to use when `at()` is called without one.
            scale: Multiplier applied to all values. Useful for normalized data.
            on_overflow: See `Trace`.
            fill_method: See `Trace`.
        """
        require_finite(scale, "Trace scale")
        df = pd.read_csv(path, index_col=0)
        if scale != 1.0:
            df = df.astype(float) * scale

        if not pd.api.types.is_numeric_dtype(df.index):
            try:
                df.index = pd.to_datetime(df.index)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"The first column of {str(path)!r} must contain offsets in seconds "
                    "or valid timestamps."
                ) from exc

        return cls(
            df,
            anchor=anchor,
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
            require_finite(elapsed, "Trace elapsed time")
        if isinstance(elapsed, timedelta):
            np_at = (
                (elapsed.days * 86400 + elapsed.seconds) * 1_000_000 + elapsed.microseconds
            ) * 1000
        elif isinstance(elapsed, int):
            np_at = elapsed * 1_000_000_000
        else:
            # Preserve timedelta's microsecond resolution for fractional seconds.
            np_at = round(elapsed * 1_000_000) * 1000
        if column is None:
            column = self.default_column

        resolved = _get_column_name(self._offsets, column)
        offsets, values = self._offsets[resolved]

        if np_at < offsets[0] or np_at > offsets[-1]:
            boundary = "before the start" if np_at < offsets[0] else "after the end"
            raise ValueError(
                f"Elapsed time {elapsed} is {boundary} of column '{resolved}' "
                f"(trace covers {_td(offsets[0])} to {_td(offsets[-1])} since sim_start). "
                "Extend the input data or shorten the simulation."
            )

        if self._regular_step is not None:
            position, remainder = divmod(np_at, self._regular_step)
            if self._fill_method == "bfill" and remainder:
                position += 1
            return values[position]
        if self._fill_method == "ffill":
            index = offsets.searchsorted(np_at, side="right") - 1
        else:
            index = offsets.searchsorted(np_at, side="left")
        return values[index]


def _get_column_name(data: dict[str, Any], column: Optional[str]) -> str:
    if column is None:
        if len(data) == 1:
            return next(iter(data.keys()))
        raise ValueError("Column needs to be specified.")
    if column in data:
        return column
    raise ValueError(f"Unknown trace column {column!r}. Available columns: {list(data)}.")


def _td(value: np.timedelta64) -> timedelta:
    """Convert a numpy timedelta64 to a Python timedelta for readable error messages."""
    return pd.Timedelta(value).to_pytimedelta()


class LiveSignal(Signal):
    """Base class for live signals with background polling.

    This class provides common functionality for signals that need to periodically
    fetch data from external sources (APIs, databases, etc.) and cache the results.

    Args:
        update_interval: Interval in seconds between data updates
        timeout: Request timeout in seconds for external calls
    """

    def __init__(self, update_interval: float = 5.0, timeout: float = 10.0):
        if (
            not math.isfinite(update_interval)
            or not math.isfinite(timeout)
            or update_interval <= 0
            or timeout <= 0
        ):
            raise ValueError("update_interval and timeout must be finite and positive.")
        self.update_interval = update_interval
        self.timeout = timeout
        self._last_update: Optional[float] = None
        self._cached_value: float = 0.0
        self._stop = Event()
        self._thread: Optional[Thread] = None

    def start(self) -> None:
        """Start background polling when the environment starts using this signal."""
        if self._stop.is_set():
            raise RuntimeError("A closed live signal cannot be reused. Create a new signal.")
        if self._thread is None:
            self._initialize()
            self._thread = Thread(
                target=self._poll, daemon=True, name=f"vessim-{type(self).__name__}"
            )
            self._thread.start()

    def _initialize(self) -> None:
        """Prepare the external source before starting a polling worker."""

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

    def _poll(self) -> None:
        while not self._stop.is_set():
            try:
                self._cached_value = self._fetch_current_value()
                self._last_update = time.time()
            except Exception:
                pass  # Retain the last observation if a source is temporarily unavailable.
            if self._stop.wait(self.update_interval):
                break

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
        self._stop.set()
        if self._thread is not None and current_thread() is not self._thread:
            self._thread.join(timeout=self.timeout + 0.1)


class PrometheusSignal(LiveSignal):
    """Signal that pulls energy usage data from a Prometheus instance.

    Args:
        url: Base URL of the Prometheus server (e.g., 'http://localhost:9090')
        query: PromQL query to fetch energy usage data
        update_interval: Interval in seconds between metric updates
        timeout: Request timeout in seconds
        username: Username for HTTP Basic Authentication (optional)
        password: Password for HTTP Basic Authentication (optional)
    """

    def __init__(
        self,
        url: str,
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
        self.prometheus_url = url.rstrip("/")
        self.query = query
        self.username = username
        self.password = password

        # Set up authentication if provided
        self._auth = None
        if username and password:
            self._auth = requests.auth.HTTPBasicAuth(username, password)

        super().__init__(update_interval=update_interval, timeout=timeout)

    def _initialize(self) -> None:
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


class WatttimeSignal(LiveSignal):
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
                "Install with: pip install 'vessim[live]'"
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
        self.timeout = timeout
        self._token: Optional[str] = None
        self._token_expires: Optional[float] = None

        self._region = region
        self._location = location
        super().__init__(update_interval=update_interval, timeout=timeout)

    def _initialize(self) -> None:
        self._get_token()
        if self._location is not None:
            self._region = self._get_region_from_location(self._location)

    def __repr__(self):
        """Returns a string representation for the Vessim viewer."""
        if self._location is not None:
            return f"WatttimeSignal(location={self._location})"
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
            response = self._requests.get(login_url, auth=self._auth, timeout=self.timeout)
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
                response = self._requests.get(login_url, auth=self._auth, timeout=self.timeout)
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

        response = self._requests.post(register_url, json=registration_data, timeout=self.timeout)
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

        response = self._requests.get(
            region_url, headers=headers, params=params, timeout=self.timeout
        )
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
