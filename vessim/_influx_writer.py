"""InfluxDB Writer for vessim simulations."""

from __future__ import annotations

import math
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Any

from loguru import logger

try:
    from influxdb_client import InfluxDBClient, WriteOptions
    from influxdb_client.client.write_api import WriteType
    INFLUX_AVAILABLE = True
except ImportError:
    INFLUX_AVAILABLE = False

if TYPE_CHECKING:
    from vessim.actor import Actor

_FLOAT_FIELD_KEYS = (
    "soc", "p_grid", "p_delta", "capacity",
    "charge_level", "charge_power", "min_soc", "c_rate",
)
_MEASUREMENT = "sim"


class InfluxWriter:
    """Batching writer for InfluxDB 2.x. Non-blocking, auto-flushes on close."""

    def __init__(self, url: str, token: str, org: str, bucket: str,
                 sim_id: Optional[str] = None) -> None:
        self._org = org
        self._bucket = bucket
        self._sim_id = sim_id
        self._client: Optional[Any] = None
        self._write_api: Optional[Any] = None
        self._closed = False
        self._points_written = 0

        if not INFLUX_AVAILABLE:
            return

        self._client = InfluxDBClient(url=url, token=token, org=org, timeout=10_000)
        self._write_api = self._client.write_api(
            write_options=WriteOptions(
                write_type=WriteType.batching,
                batch_size=500,
                flush_interval=1_000,
                retry_interval=5_000,
                max_retries=3,
                max_retry_delay=30_000,
            ),
            success_callback=self._on_success,
            error_callback=self._on_error,
            retry_callback=self._on_retry,
        )
        logger.info(f"InfluxWriter connected to InfluxDB at {url}")

    def _on_success(self, conf: tuple, data: Any) -> None:
        if data:
            s = data.decode("utf-8") if isinstance(data, bytes) else str(data)
            self._points_written += s.count("\n") + 1

    def _on_error(self, conf: tuple, data: Any, exc: Exception) -> None:
        logger.error(f"InfluxDB write failed: {exc}")

    def _on_retry(self, conf: tuple, data: Any, exc: Exception) -> None:
        logger.warning(f"InfluxDB retry: {exc}")

    @property
    def is_available(self) -> bool:
        return INFLUX_AVAILABLE and self._write_api is not None and not self._closed

    @property
    def points_written(self) -> int:
        return self._points_written

    def write_microgrid(
        self,
        ts: datetime,
        microgrid_name: str,
        actor_values: dict["Actor", float],
        microgrid_state: dict,
        coords: Optional[tuple[float, float]] = None,
        tag_sums: Optional[dict[str, float]] = None,
    ) -> None:
        """Write actor data and microgrid state for a single microgrid."""
        if not self.is_available:
            return

        lines: list[str] = []
        ts_ns = int(ts.timestamp() * 1e9)

        for actor, value in actor_values.items():
            fval = _to_float(value)
            if fval is None:
                continue
            category = _escape(actor.tag) if actor.tag else "unknown"
            tags = f"category={category},name={_escape(actor.name)}"
            tags += f",microgrid={_escape(microgrid_name)}"
            if self._sim_id:
                tags += f",sim_id={_escape(self._sim_id)}"
            if actor.coords is not None:
                tags += f",lat={actor.coords[0]},lon={actor.coords[1]}"
            lines.append(f"{_MEASUREMENT},{tags} value={fval} {ts_ns}")

        mg_tags = f"category=microgrid,name={_escape(microgrid_name)}"
        mg_tags += f",microgrid={_escape(microgrid_name)}"
        if self._sim_id:
            mg_tags += f",sim_id={_escape(self._sim_id)}"
        if coords is not None:
            mg_tags += f",lat={coords[0]},lon={coords[1]}"

        storage_state = microgrid_state.get("storage_state") or {}
        policy_state = microgrid_state.get("policy_state") or {}
        flat = {
            "soc": storage_state.get("soc"),
            "p_grid": microgrid_state.get("p_grid"),
            "p_delta": microgrid_state.get("p_delta"),
            "capacity": storage_state.get("capacity"),
            "charge_level": storage_state.get("charge_level"),
            "charge_power": policy_state.get("charge_power"),
            "min_soc": storage_state.get("min_soc"),
            "c_rate": storage_state.get("c_rate"),
        }

        fields: list[str] = []
        for key in _FLOAT_FIELD_KEYS:
            fval = _to_float(flat.get(key))
            if fval is not None:
                fields.append(f"{key}={fval}")

        mode = policy_state.get("mode")
        if mode is not None:
            fields.append(f'mode="{_escape(str(mode))}"')

        if tag_sums:
            for tag, val in tag_sums.items():
                fval = _to_float(val)
                if fval is not None:
                    fields.append(f"tag_sum_{_escape(tag)}={fval}")

        if fields:
            lines.append(f"{_MEASUREMENT},{mg_tags} {','.join(fields)} {ts_ns}")

        if lines and self._write_api is not None:
            self._write_api.write(
                bucket=self._bucket, org=self._org, record="\n".join(lines),
            )

    def close(self) -> None:
        """Flush and close."""
        if self._closed:
            return
        self._closed = True
        if self._write_api:
            self._write_api.close()
            logger.info(f"InfluxWriter closed: {self._points_written} points written")
            self._write_api = None
        if self._client:
            self._client.close()
            self._client = None


def _to_float(value: Any) -> Optional[float]:
    """Convert to float, returning None for non-finite or invalid values."""
    if value is None:
        return None
    try:
        fval = float(value)
        return None if math.isnan(fval) or math.isinf(fval) else fval
    except (TypeError, ValueError):
        return None


def _escape(value: str) -> str:
    """Escape InfluxDB line protocol special characters in tag values."""
    if not value:
        return "unknown"
    return str(value).replace("\\", "\\\\").replace(" ", "\\ ").replace(",", "\\,").replace("=", "\\=")
