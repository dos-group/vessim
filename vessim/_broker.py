import threading
from collections import defaultdict
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import HTMLResponse


class PrometheusMetrics:
    """Encapsulates all Prometheus metrics for Vessim."""

    def __init__(self):
        try:
            from prometheus_client import Counter, Gauge
        except ImportError as e:
            raise ImportError(
                "prometheus_client is required for Prometheus metrics export. "
                "Install with: pip install vessim[sil]"
            ) from e

        self.microgrid_p_delta = Gauge(
            'vessim_microgrid_p_delta',
            'Current power consumption/production of microgrid',
            ['microgrid']
        )
        self.microgrid_p_grid = Gauge(
            'vessim_microgrid_p_grid',
            'Current grid power exchange',
            ['microgrid']
        )
        self.dispatchable_soc = Gauge(
            'vessim_dispatchable_soc',
            'Dispatchable state of charge (0-1)',
            ['microgrid', 'dispatchable']
        )
        self.dispatchable_capacity_wh = Gauge(
            'vessim_dispatchable_capacity_wh',
            'Dispatchable capacity in Wh',
            ['microgrid', 'dispatchable']
        )
        self.microgrid_p_actor = Gauge(
            'vessim_microgrid_p_actor',
            'Power consumption/production by actor',
            ['microgrid', 'actor']
        )
        self.data_points_total = Counter(
            'vessim_data_points_total',
            'Total number of data points received',
            ['microgrid']
        )

    def update_from_data(self, microgrid_name: str, data: dict[str, Any]):
        """Update all metrics from incoming simulation data."""
        self.data_points_total.labels(microgrid=microgrid_name).inc()

        if 'p_delta' in data:
            self.microgrid_p_delta.labels(microgrid=microgrid_name).set(data['p_delta'])
        if 'p_grid' in data:
            self.microgrid_p_grid.labels(microgrid=microgrid_name).set(data['p_grid'])

        # Dispatchable metrics from dispatch_states
        dispatch_states = data.get('dispatch_states')
        if isinstance(dispatch_states, dict):
            for name, state in dispatch_states.items():
                if isinstance(state, dict):
                    if 'soc' in state:
                        self.dispatchable_soc.labels(
                            microgrid=microgrid_name, dispatchable=name
                        ).set(state['soc'])
                    if 'capacity' in state:
                        self.dispatchable_capacity_wh.labels(
                            microgrid=microgrid_name, dispatchable=name
                        ).set(state['capacity'])

        # Actor power metrics from actor_states
        actor_states = data.get('actor_states')
        if isinstance(actor_states, dict):
            for actor_name, state in actor_states.items():
                if isinstance(state, dict) and 'power' in state:
                    self.microgrid_p_actor.labels(
                        microgrid=microgrid_name, actor=actor_name
                    ).set(state['power'])


class Broker:
    def __init__(self, export_prometheus: bool = False):
        self.microgrids: dict[str, dict] = {}
        self.history: dict[str, list] = defaultdict(list)
        self.commands: list[dict] = []
        self.lock = threading.Lock()
        self.metrics = PrometheusMetrics() if export_prometheus else None

    def add_microgrid(self, name: str, config: dict[str, Any]):
        self.microgrids[name] = config

    def push_data(self, microgrid_name: str, data: dict[str, Any]):
        with self.lock:
            self.history[microgrid_name].append(data)
            if self.metrics:
                self.metrics.update_from_data(microgrid_name, data)

    def get_commands(self) -> list[dict]:
        with self.lock:
            commands = self.commands.copy()
            self.commands.clear()
            return commands

    def add_command(self, command: dict[str, Any]):
        with self.lock:
            self.commands.append(command)


broker = Broker()
app = FastAPI(title="Vessim API")



@app.get("/", response_class=HTMLResponse)
def read_root():
    return """
    <html>
        <head><title>Vessim API</title></head>
        <body style="font-family: Arial, sans-serif; margin: 20px;">
            <h1>Vessim API</h1>
            <p>
                Full API documentation:
                <a href="/docs">Swagger UI</a> / <a href="/redoc">ReDoc</a>
            </p>
        </body>
    </html>
    """


# User-facing API
@app.get("/microgrids")
def list_microgrids() -> list[str]:
    return list(broker.microgrids.keys())


@app.get("/microgrids/{name}/config")
def get_microgrid_config_detail(name: str):
    if name not in broker.microgrids:
        raise HTTPException(404, "Microgrid not found")
    return broker.microgrids[name]


@app.get("/microgrids/{name}")
def get_microgrid_state(name: str):
    if name not in broker.microgrids:
        raise HTTPException(404, "Microgrid not found")
    if name not in broker.history or not broker.history[name]:
        raise HTTPException(404, "No data available")
    return broker.history[name][-1]


@app.get("/microgrids/{name}/history")
def get_history(name: str, limit: int = 100):
    if name not in broker.history:
        raise HTTPException(404, "Microgrid not found")
    history = list(broker.history[name])
    return {"data": history[-limit:] if limit else history}


@app.put("/microgrids/{name}/dispatchables/{dispatchable_name}/{prop}")
def set_dispatchable_prop(name: str, dispatchable_name: str, prop: str, value: Any):
    broker.add_command({
        "type": "set_parameter",
        "microgrid": name,
        "target": "dispatchable",
        "target_name": dispatchable_name,
        "property": prop,
        "value": value,
    })
    return {"status": "command queued"}


@app.put("/microgrids/{name}/policy/{prop}")
def set_policy_prop(name: str, prop: str, value: Any):
    broker.add_command({
        "type": "set_parameter",
        "microgrid": name,
        "target": "policy",
        "property": prop,
        "value": value,
    })
    return {"status": "command queued"}


@app.put("/microgrids/{name}/actors/{actor_name}/signal")
def set_actor_signal(name: str, actor_name: str, value: float):
    broker.add_command({
        "type": "set_parameter",
        "microgrid": name,
        "target": "actor",
        "target_name": actor_name,
        "property": "value",
        "value": value,
    })
    return {"status": "command queued"}


# Prometheus metrics endpoint
@app.get("/metrics")
def get_prometheus_metrics():
    if broker.metrics is None:
        raise HTTPException(404, "Prometheus metrics not enabled")
    try:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    except ImportError as e:
        raise ImportError(
            "prometheus_client is required for Prometheus metrics export. "
            "Install with: pip install vessim[sil]"
        ) from e
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Simulation-facing API
@app.post("/internal/microgrids/{name}")
def register_microgrid(name: str, config: dict[str, Any]):
    broker.add_microgrid(name, config)
    return {"status": "ok"}


@app.post("/internal/data/{microgrid_name}")
def push_data(microgrid_name: str, data: dict[str, Any]):
    broker.push_data(microgrid_name, data)
    return {"status": "ok"}


@app.get("/internal/commands")
def get_commands():
    return {"commands": broker.get_commands()}


def run_broker(port: int = 8700, export_prometheus: bool = False):
    global broker
    broker = Broker(export_prometheus=export_prometheus)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
