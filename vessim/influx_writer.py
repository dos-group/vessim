"""InfluxDB Writer for vessim simulations."""

from __future__ import annotations

import math
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Any

try:
    from influxdb_client import InfluxDBClient, WriteOptions
    from influxdb_client.client.write_api import WriteType
    INFLUX_AVAILABLE = True
except ImportError:
    INFLUX_AVAILABLE = False

if TYPE_CHECKING:
    from vessim.actor import Actor

logger = logging.getLogger(__name__)


@dataclass
class InfluxConfig:
    """InfluxDB connection and batching config."""
    url: str
    token: str
    org: str
    bucket: str
    enabled: bool = True
    batch_size: int = 500
    flush_interval_ms: int = 1000
    timeout_ms: int = 10_000
    retry_interval_ms: int = 5000
    max_retries: int = 3
    max_retry_delay_ms: int = 30_000
    measurement: str = "sim"


class InfluxWriter:
    """Batching writer for InfluxDB 2.x. Non-blocking, auto-flushes on close."""
    
    def __init__(self, config: InfluxConfig) -> None:
        self._config = config
        self._client: Optional[Any] = None
        self._write_api: Optional[Any] = None
        self._closed = False
        self._points_written = 0
        
        if not config.enabled or not INFLUX_AVAILABLE:
            return
        
        self._client = InfluxDBClient(
            url=config.url, token=config.token, org=config.org, timeout=config.timeout_ms
        )
        self._write_api = self._client.write_api(
            write_options=WriteOptions(
                write_type=WriteType.batching,
                batch_size=config.batch_size,
                flush_interval=config.flush_interval_ms,
                retry_interval=config.retry_interval_ms,
                max_retries=config.max_retries,
                max_retry_delay=config.max_retry_delay_ms,
            ),
            success_callback=self._on_success,
            error_callback=self._on_error,
            retry_callback=self._on_retry,
        )
        logger.info(f"InfluxWriter: {config.url} bucket={config.bucket}")
    
    def _on_success(self, conf: tuple, data: Any) -> None:
        if data:
            s = data.decode('utf-8') if isinstance(data, bytes) else str(data)
            self._points_written += s.count('\n') + 1
    
    def _on_error(self, conf: tuple, data: Any, exc: Exception) -> None:
        logger.error(f"InfluxDB write failed: {exc}")
    
    def _on_retry(self, conf: tuple, data: Any, exc: Exception) -> None:
        logger.warning(f"InfluxDB retry: {exc}")
    
    @property
    def is_available(self) -> bool:
        return self._config.enabled and INFLUX_AVAILABLE and self._write_api is not None and not self._closed
    
    @property
    def points_written(self) -> int:
        return self._points_written
    
    def write_batch(
        self,
        ts: datetime,
        actor_values: dict["Actor", float],
        microgrid: Optional[str] = None,
        sim_id: Optional[str] = None,
        # Microgrid-level state (all fields from CSV)
        soc: Optional[float] = None,
        p_grid: Optional[float] = None,
        p_delta: Optional[float] = None,
        coords: Optional[tuple[float, float]] = None,
        # Storage state
        capacity: Optional[float] = None,
        charge_level: Optional[float] = None,
        charge_power: Optional[float] = None,
        min_soc: Optional[float] = None,
        c_rate: Optional[float] = None,
        # Policy state
        mode: Optional[str] = None,
        # Tag sums
        tag_sums: Optional[dict[str, float]] = None,
    ) -> None:
        """Write actor values + full microgrid state. Schema: measurement=sim, tags={microgrid,category,name}, fields=..."""
        if not self.is_available:
            return
        
        lines: list[str] = []
        measurement = self._config.measurement
        ts_ns = int(ts.timestamp() * 1e9)
        
        # Write actor values (+ actor coords if available)
        for actor, value in actor_values.items():
            if value is None:
                continue
            try:
                fval = float(value)
                if math.isnan(fval) or math.isinf(fval):
                    continue
            except (TypeError, ValueError):
                continue
            
            category = _escape(actor.tag) if actor.tag else "unknown"
            name = _escape(actor.name) if actor.name else "unknown"
            tags = f"category={category},name={name}"
            if microgrid:
                tags += f",microgrid={_escape(microgrid)}"
            if sim_id:
                tags += f",sim_id={_escape(sim_id)}"
            
            # Add actor coords as tags (not fields)
            if hasattr(actor, 'coords') and actor.coords is not None and len(actor.coords) == 2:
                try:
                    alat, alon = float(actor.coords[0]), float(actor.coords[1])
                    tags += f",lat={alat},lon={alon}"
                except (TypeError, ValueError):
                    pass
            
            lines.append(f"{measurement},{tags} value={fval} {ts_ns}")
        
        # Write microgrid-level metrics (all fields from CSV)
        if microgrid:
            mg_tags = f"category=microgrid,name={_escape(microgrid)}"
            mg_tags += f",microgrid={_escape(microgrid)}"
            if sim_id:
                mg_tags += f",sim_id={_escape(sim_id)}"
            
            # Add microgrid coords as tags
            if coords is not None and len(coords) == 2:
                try:
                    lat, lon = float(coords[0]), float(coords[1])
                    mg_tags += f",lat={lat},lon={lon}"
                except (TypeError, ValueError):
                    pass
            
            fields: list[str] = []
            
            # Helper to add float field
            def add_float(name: str, val: Optional[float]) -> None:
                if val is not None:
                    try:
                        fv = float(val)
                        if not (math.isnan(fv) or math.isinf(fv)):
                            fields.append(f"{name}={fv}")
                    except (TypeError, ValueError):
                        pass
            
            add_float("soc", soc)
            add_float("p_grid", p_grid)
            add_float("p_delta", p_delta)
            add_float("capacity", capacity)
            add_float("charge_level", charge_level)
            add_float("charge_power", charge_power)
            add_float("min_soc", min_soc)
            add_float("c_rate", c_rate)
            
            # Mode as string field (quoted)
            if mode is not None:
                fields.append(f'mode="{_escape(str(mode))}"')
            
            # Tag sums
            if tag_sums:
                for tag, val in tag_sums.items():
                    add_float(f"tag_sum_{_escape(tag)}", val)
            
            if fields:
                lines.append(f"{measurement},{mg_tags} {','.join(fields)} {ts_ns}")
        
        if lines:
            self._write_api.write(bucket=self._config.bucket, org=self._config.org, record="\n".join(lines))
    
    def close(self) -> None:
        """Flush and close."""
        if self._closed:
            return
        self._closed = True
        
        if self._write_api:
            self._write_api.close()
            logger.info(f"InfluxWriter closed: {self._points_written} points")
            self._write_api = None
        if self._client:
            self._client.close()
            self._client = None
    
    def __enter__(self) -> "InfluxWriter":
        return self
    
    def __exit__(self, *args: Any) -> None:
        self.close()


def _escape(value: str) -> str:
    """Escape InfluxDB tag special chars."""
    if not value:
        return "unknown"
    return str(value).replace("\\", "\\\\").replace(" ", "\\ ").replace(",", "\\,").replace("=", "\\=")
