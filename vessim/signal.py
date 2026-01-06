from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import timedelta
from pathlib import Path
from typing import Any, Optional, Literal
from itertools import count

import time
import pandas as pd
import numpy as np

from vessim._data import load_dataset
from vessim._util import DatetimeLike


class Signal(ABC):
    """Abstract base class for signals."""

    @abstractmethod
    def now(self, at: Optional[DatetimeLike] = None, **kwargs) -> float:
        """Retrieves actual data point at given time."""

    def finalize(self) -> None:
        """Perform necessary finalization tasks of a signal."""


class StaticSignal(Signal):
    _ids = count(0)

    def __init__(self, value: float) -> None:
        self._v = value

    def __repr__(self):
        """Returns a string representation of the StaticSignal."""
        return f"StaticSignal({self._v})"

    def set_value(self, value: float) -> None:
        self._v = value

    def now(self, at: Optional[DatetimeLike] = None, **kwargs):
        return self._v


class Trace(Signal):
    """Simulates a signal for time-series data like solar irradiance or carbon intensity.

    The Trace can also deal with unsorted or incomplete data.

    Args:
        actual: The actual time-series data to be used. It should contain a datetime-like
            index marking the time, and each column should represent a different zone
            containing the data. The name of the zone is equal to the column name.
            Note that while interpolation is possible when retrieving forecasts, the
            actual data between timestamps is computed using either `ffill` or `bfill`.
            If you wish a different behavior, you have to change your actual data
            beforehand (e.g. by resampling into a different frequency).

        forecast: An optional time-series dataset representing forecasted values. The
            data should contain two datetime-like indices. One is the
            `Request Timestamp`, marking the time when the forecast was made. One is the
            `Forecast Timestamp`, indicating the time the forecast is made for.

            - If data does not include a `Request Timestamp`, it is treated as a static
              forecast that does not change over time.

            - If `forecast` is not provided, predictions are derived from the actual
              data when requesting forecasts (actual data is treated as static forecast).

        fill_method: Either `ffill` or `bfill`. Determines how actual data is acquired in
            between timestamps. Default is `ffill`.

        column: Default column to be used if no column is specified for at().
            Defaults to None.
    """

    def __init__(
        self,
        actual: pd.Series | pd.DataFrame,
        forecast: Optional[pd.Series | pd.DataFrame] = None,
        fill_method: Literal["ffill", "bfill"] = "ffill",
        column: Optional[str] = None,
        repr_: Optional[str] = None,
    ):
        if isinstance(actual, pd.DataFrame) and forecast is not None:
            if isinstance(forecast, pd.DataFrame):
                if not actual.columns.equals(forecast.columns):
                    raise ValueError("Column names in actual and forecast do not match.")
            else:
                raise ValueError("Forecast has to be a DataFrame if actual is a DataFrame.")

        self._fill_method = fill_method
        self.default_column = column
        self.repr_ = repr_

        # Unpack index of actual dataframe
        actual_times = actual.index.to_numpy(dtype="datetime64[ns]", copy=True)
        actual_times_sorter = actual_times.argsort()
        actual_times = actual_times[actual_times_sorter]

        # Unpack values of actual dataframe
        self._actual: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        if isinstance(actual, pd.Series):
            actual_values = actual.to_numpy(dtype=float, copy=True)[actual_times_sorter]
            nan_mask = ~np.isnan(actual_values)
            self._actual[str(actual.name)] = actual_times[nan_mask], actual_values[nan_mask]
        elif isinstance(actual, pd.DataFrame):
            for col in actual.columns:
                actual_values = actual[col].to_numpy(dtype=float, copy=True)[actual_times_sorter]
                nan_mask = ~np.isnan(actual_values)
                self._actual[str(col)] = actual_times[nan_mask], actual_values[nan_mask]
        else:
            raise ValueError(f"Incompatible type {type(actual)} for 'actual'.")

        # Unpack indices of forecast dataframe if present
        forecast_request_times: Optional[np.ndarray] = None
        if isinstance(forecast, (pd.Series, pd.DataFrame)):
            if isinstance(forecast.index, pd.MultiIndex):
                forecast_request_times = forecast.index.get_level_values(0).to_numpy(
                    dtype="datetime64[ns]", copy=True
                )
                forecast_times = forecast.index.get_level_values(1).to_numpy(
                    dtype="datetime64[ns]", copy=True
                )
                forecast_times_sorter = np.lexsort((forecast_times, forecast_request_times))
                forecast_request_times = forecast_request_times[forecast_times_sorter]
            else:
                forecast_times = forecast.index.to_numpy(dtype="datetime64[ns]", copy=True)
                forecast_times_sorter = np.argsort(forecast_times)
            forecast_times = forecast_times[forecast_times_sorter]

        # Unpack values of forecast dataframe if present
        self._forecast: Optional[dict[str, tuple[Optional[np.ndarray], np.ndarray, np.ndarray]]]
        self._forecast = None
        if forecast_request_times is None:
            req_times = None

        if isinstance(forecast, pd.Series):
            values = forecast.to_numpy(dtype=float, copy=True)[forecast_times_sorter]
            nan_mask = ~np.isnan(values)
            if forecast_request_times is not None:
                req_times = forecast_request_times[nan_mask]
            self._forecast = {
                str(forecast.name): (req_times, forecast_times[nan_mask], values[nan_mask])
            }
        elif isinstance(forecast, pd.DataFrame):
            self._forecast = {}
            for col in forecast.columns:
                values = forecast[col].to_numpy(dtype=float, copy=True)[forecast_times_sorter]
                nan_mask = ~np.isnan(values)
                if forecast_request_times is not None:
                    req_times = forecast_request_times[nan_mask]
                self._forecast[str(col)] = (req_times, forecast_times[nan_mask], values[nan_mask])
        elif forecast is not None:
            raise ValueError(f"Incompatible type {type(forecast)} for 'forecast'.")

    def __repr__(self):
        """Returns a string representation of the Trace."""
        return f"Trace({self.repr_ or ''})"

    @classmethod
    def load(
        cls,
        dataset: str,
        column: Optional[str] = None,
        data_dir: Optional[str | Path] = None,
        params: Optional[dict[Any, Any]] = None,
    ):
        """Creates a Trace from a vessim dataset, handling downloading and unpacking.

        Args:
            dataset: Name of the dataset to be downloaded.
            column: Default column to use for calling Trace.at().
                Default to None.
            data_dir: Absoulute path to the directory where the data should be loaded.
                If not specified, the path `~/.cache/vessim` is used. Defaults to None.
            params: Optional extra parameters used for data loading.
                scale (float): Multiplies the data with a factor. Default: 1.0
                start_time (DatetimeLike): Shifts data so that it starts at time. Default: None
                use_forecast (bool): Determines if forecast should be loaded. Default: True
        Raises:
            ValueError if dataset is not available or invalid params are given.
            RuntimeError if dataset can not be loaded.
        """
        if params is None:
            params = {}
        return cls(**load_dataset(dataset, _abs_path(data_dir), params), column=column)

    def columns(self) -> list:
        """Returns a list of all columns where actual data is available."""
        return list(self._actual.keys())

    def now(
        self,
        at: Optional[DatetimeLike] = None,
        column: Optional[str] = None,
        **kwargs: dict[str, Any],
    ) -> float:
        """Retrieves actual data point of zone at given time.

        If queried timestamp is not available in the `actual` dataframe, the fill_method
        is used to determine the data point.

        Args:
            at: Timestamp, at which data is returned.
            column: Optional column for the data. Has to be provided if there is more than one
                column specified in the data. Defaults to None.
            **kwargs: Possibly needed for subclasses. Are not supported in this class and a
                ValueError will be raised if specified.

        Raises:
            ValueError: If there is no available data at zone or time, or extra kwargs specified.
        """
        if at is None:
            raise ValueError("Argument at cannot be None.")
        if kwargs:
            raise ValueError(f"Invalid arguments: {kwargs.keys()}")
        if column is None:
            column = self.default_column

        np_dt = np.datetime64(at)
        times, values = self._actual[_get_column_name(self._actual, column)]

        if self._fill_method == "ffill":
            index = times.searchsorted(np_dt, side="right") - 1
            if index >= 0:
                return values[index]
            else:
                raise ValueError(f"'{at}' is too early to get data in column '{column}'.")
        else:
            index = times.searchsorted(np_dt, side="left")
            try:
                return values[index]
            except IndexError:
                raise ValueError(f"'{at}' is too late to get data in column '{column}'.")

    def forecast(
        self,
        start_time: DatetimeLike,
        end_time: DatetimeLike,
        column: Optional[str] = None,
        frequency: Optional[str | timedelta] = None,
        resample_method: Optional[Literal["ffill", "bfill", "linear", "nearest"]] = None,
    ) -> dict[np.datetime64, float]:
        """Retrieves forecasted data points within window at a frequency.

        - If no separate forecast time-series data is provided, actual data is used.
        - If frequency is not specified, all existing data in the window will be returned.
        - If there is more than one column present, it has to be specified.
        - With specified resampling methods except "bfill", the actual value valid at `start_time`
          is used and because of that, the column where data is aquired has to appear in this data.
        - The forecast does not include the value at `start_time` (see example).

        Args:
            start_time: Starting time of the window.
            end_time: End time of the window.
            column: Optional column where data should be used.
            frequency: Optional interval, in which the forecast data is to be provided.
                Defaults to None.
            resample_method: Optional method, to deal with holes in resampled data.
                Options are `ffill`, `bfill`, `linear` and `nearest`. Defaults to None.

        Returns:
            pd.Series of forecasted data with timestamps of forecast as index.

        Raises:
            ValueError: If no data is available for the specified zone or time, or if
                insufficient data exists for the frequency, without `resample_method`
                specified.

        Example:
            >>> index = pd.date_range(
            ...    "2020-01-01T00:00:00", "2020-01-01T03:00:00", freq="1h"
            ... )
            >>> actual = pd.DataFrame({"zone_a": [4, 6, 2, 8]}, index=index)

            >>> forecast_data = [
            ...    ["2020-01-01T00:00:00", "2020-01-01T01:00:00", 5],
            ...    ["2020-01-01T00:00:00", "2020-01-01T02:00:00", 2],
            ...    ["2020-01-01T00:00:00", "2020-01-01T03:00:00", 6],
            ... ]
            >>> forecast = pd.DataFrame(
            ...    forecast_data, columns=["req_time", "forecast_time", "zone_a"]
            ... )
            >>> forecast.set_index(["req_time", "forecast_time"], inplace=True)

            >>> signal = Trace(actual, forecast)

            Forward-fill resampling between 2020-01-01T00:00:00 (actual value = 4.0) and
            forecasted values between 2020-01-01T01:00:00 and 2020-01-01T02:00:00:

            >>> signal.forecast(
            ...    start_time="2020-01-01T00:00:00",
            ...    end_time="2020-01-01T02:00:00",
            ...    frequency="30min",
            ...    resample_method="ffill",
            ... )
            {numpy.datetime64('2020-01-01T00:30:00'): 4.0,
            numpy.datetime64('2020-01-01T01:00:00'): 5.0,
            numpy.datetime64('2020-01-01T01:30:00'): 5.0,
            numpy.datetime64('2020-01-01T02:00:00'): 2.0}

            Time interpolation between 2020-01-01T01:10:00 (actual value = 6.0) and
            2020-01-01T02:00:00 (forecasted value = 2.0):

            >>> signal.forecast(
            ...    start_time="2020-01-01T01:10:00",
            ...    end_time="2020-01-01T01:55:00",
            ...    zone="zone_a",
            ...    frequency=timedelta(minutes=20),
            ...    resample_method="time",
            ... )
            {numpy.datetime64('2020-01-01T01:30:00'): 4.4,
            numpy.datetime64('2020-01-01T01:50:00'): 2.8}
        """
        if column is None:
            column = self.default_column

        np_start = np.datetime64(start_time)
        np_end = np.datetime64(end_time)
        if self._forecast is None:
            # No error forecast (actual data is used as static forecast)
            column_name = _get_column_name(self._actual, column)
            times, forecast = self._actual[column_name]
        else:
            column_name = _get_column_name(self._forecast, column)
            req_times, times, forecast = self._forecast[column_name]
            if req_times is not None:
                # Non-static forecast
                req_end_index = np.searchsorted(req_times, np_start, side="right")
                if req_end_index <= 0:
                    raise ValueError(f"No forecasts available at time {start_time}.")
                req_start_index = np.searchsorted(
                    req_times, req_times[req_end_index - 1], side="left"
                )
                times = times[req_start_index:req_end_index]
                forecast = forecast[req_start_index:req_end_index]

        # Resample the data to get the data to specified frequency
        if frequency is not None:
            np_freq = np.timedelta64(pd.to_timedelta(frequency))
            return self._resample_to_frequency(
                times, forecast, column_name, np_start, np_end, np_freq, resample_method
            )

        start_index = np.searchsorted(times, np_start, side="right")
        end_index = np.searchsorted(times, np_end, side="right")
        return dict(
            zip(times[start_index:end_index].copy(), forecast[start_index:end_index].copy())
        )

    def _resample_to_frequency(
        self,
        times: np.ndarray,
        data: np.ndarray,
        column: str,
        start_time: np.datetime64,
        end_time: np.datetime64,
        freq: np.timedelta64,
        resample_method: Optional[Literal["ffill", "bfill", "linear", "nearest"]],
    ) -> dict[np.datetime64, float]:
        """Transform frame into the desired frequency between start and end time."""
        # Cutoff data and create deep copy
        start_index = np.searchsorted(times, start_time, side="right")
        if start_index >= times.size:
            raise ValueError(f"No data found at start time '{start_time}'.")
        end_index = np.searchsorted(times, end_time, side="right") + 1
        times = times[start_index:end_index].copy()
        data = data[start_index:end_index].copy()

        new_times = np.arange(
            start_time + freq, end_time + np.timedelta64(1, "ns"), freq, dtype="datetime64[ns]"
        )

        new_times_indices = np.searchsorted(times, new_times, side="left")
        if np.all(new_times_indices < times.size) and np.array_equal(
            new_times, times[new_times_indices]
        ):
            # No resampling necessary
            new_data = data[new_times_indices]
        elif resample_method == "bfill":
            # Perform backward-fill whereas values outside range are filled with NaN
            new_data = np.full(new_times_indices.shape, np.nan)
            valid_mask = new_times_indices < len(data)
            new_data[valid_mask] = data[new_times_indices[valid_mask]]
        else:
            # Actual value is used for interpolation
            times = np.insert(times, 0, start_time)
            # https://github.com/dos-group/vessim/issues/234
            # Use the length of the actual data to determine the column:
            # self._actual is a dict[str, tuple[np.ndarray, np.ndarray]]
            # -> every key is a column name
            # -> if len(self._actual) == 1, _actual is based on pd.Series and column is None
            data = np.insert(
                data, 0, self.now(start_time, None if len(self._actual) == 1 else column)
            )
            if resample_method == "ffill":
                new_data = data[np.searchsorted(times, new_times, side="right") - 1]
            elif resample_method == "nearest":
                spacing = np.diff(times) / 2
                times = times + np.hstack([spacing, spacing[-1]])
                data = np.hstack([data, data[-1]])
                new_data = data[np.searchsorted(times, new_times)]
            elif resample_method == "linear":
                # Numpy does not support interpolation on datetimes
                new_data = np.interp(new_times.astype("float64"), times.astype("float64"), data)
            elif resample_method is not None:
                raise ValueError(f"Unknown resample_method '{resample_method}'.")
            else:
                raise ValueError(f"Not enough data at frequency '{freq}' without resampling.")

        return dict(zip(new_times, new_data))


def _get_column_name(data: dict[str, Any], column: Optional[str]) -> str:
    """Extracts data from a dictionary at a key."""
    if column is None:
        if len(data) == 1:
            return next(iter(data.keys()))
        else:
            raise ValueError("Column needs to be specified.")
    elif column in data.keys():
        return column
    else:
        raise ValueError(f"Cannot retrieve data for column '{column}'.")


def _abs_path(data_dir: Optional[str | Path]) -> Path:
    """Returns absolute path to the directory data should be loaded into."""
    if data_dir is None:
        return Path.home() / ".cache" / "vessim"

    path = Path(data_dir).expanduser()
    if path.is_absolute():
        return path
    else:
        raise ValueError(f"Path {data_dir} not valid. Has to be absolute or None.")


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

    def now(self, at: Optional[DatetimeLike] = None, **kwargs: dict[str, Any]) -> float:
        """Return the current cached value.

        Args:
            at: Current simulation time (ignored for real-time data)
            **kwargs: Additional parameters (ignored)

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
        consumer: If True, negates values (Vessim represents consumption as negative)
        username: Username for HTTP Basic Authentication (optional)
        password: Password for HTTP Basic Authentication (optional)
    """

    def __init__(
        self,
        prometheus_url: str,
        query: str,
        consumer: bool = True,
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
        self.consumer = consumer
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
        response = self.requests.get(
            f"{self.prometheus_url}/api/v1/query",
            params={"query": "up"},
            timeout=self.timeout,
            auth=self._auth,
        )
        response.raise_for_status()

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
        value = float(results[0]["value"][1])
        return -value if self.consumer else value


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
