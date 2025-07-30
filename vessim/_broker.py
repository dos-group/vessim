import threading
from collections import defaultdict
from typing import Any

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import HTMLResponse
import uvicorn
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST


class Broker:
    def __init__(self):
        self.microgrids: dict[str, dict] = {}
        self.history: dict[str, list] = defaultdict(list)
        self.commands: list[dict] = []
        self.lock = threading.Lock()

    def add_microgrid(self, name: str, config: dict[str, Any]):
        self.microgrids[name] = config

    def push_data(self, microgrid_name: str, data: dict[str, Any]):
        with self.lock:
            self.history[microgrid_name].append(data)
            self._update_prometheus_metrics(microgrid_name, data)

    def _update_prometheus_metrics(self, microgrid_name: str, data: dict[str, Any]):
        # Update data points counter
        data_points_total.labels(microgrid=microgrid_name).inc()

        # Update power metrics
        if 'p_delta' in data:
            microgrid_p_delta.labels(microgrid=microgrid_name).set(data['p_delta'])
        if 'p_grid' in data:
            microgrid_p_grid.labels(microgrid=microgrid_name).set(data['p_grid'])

        # Update battery metrics
        for key, value in data.items():
            if key.endswith('.storage.Storage') and isinstance(value, dict):
                storage_data = value.get('storage', {})
                if 'soc' in storage_data:
                    microgrid_battery_soc.labels(microgrid=microgrid_name).set(storage_data['soc'])
                if 'capacity' in storage_data:
                    microgrid_battery_capacity_wh.labels(microgrid=microgrid_name).set(storage_data['capacity'])

        # Update actor power metrics
        for key, value in data.items():
            if '.actor.' in key and isinstance(value, dict) and 'p' in value:
                actor_name = key.split('.actor.')[1] if '.actor.' in key else key
                microgrid_p_actor.labels(
                    microgrid=microgrid_name, actor=actor_name
                ).set(value['p'])

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

# Prometheus metrics
microgrid_p_delta = Gauge('vessim_microgrid_p_delta',
                          'Current power consumption/production of microgrid',
                          ['microgrid'])
microgrid_p_grid = Gauge('vessim_microgrid_p_grid',
                         'Current grid power exchange',
                         ['microgrid'])
microgrid_battery_soc = Gauge('vessim_microgrid_battery_soc',
                              'Battery state of charge (0-1)',
                              ['microgrid'])
microgrid_battery_capacity_wh = Gauge('vessim_microgrid_battery_capacity_wh',
                                      'Battery capacity in Wh',
                                      ['microgrid'])
microgrid_p_actor = Gauge('vessim_microgrid_p_actor',
                           'Power consumption/production by actor',
                           ['microgrid', 'actor'])
data_points_total = Counter('vessim_data_points_total',
                           'Total number of data points received',
                           ['microgrid'])



@app.get("/", response_class=HTMLResponse)
def read_root():
    return """
    <html>
        <head><title>Vessim API</title></head>
        <body style="font-family: Arial, sans-serif; margin: 20px;">
            <h1>Vessim API</h1>
            <p>
                Full API documentation: 
                <a href="/docs">Swagger UI</a> / 
                <a href="/redoc">ReDoc</a>
            </p>
            <p>Run the GUI via: 
            <code style="background: #333; color: #fff; padding: 4px; border-radius: 4px;">
                streamlit run gui/app.py
            </code>
            </p>
        </body>
    </html>
    """


# User-facing API
@app.get("/microgrids")
def list_microgrids() -> list[str]:
    return list(broker.microgrids.keys())


@app.get("/microgrids/{name}")
def get_microgrid_config(name: str):
    if name not in broker.microgrids:
        raise HTTPException(404, "Microgrid not found")
    if name not in broker.history or not broker.history[name]:
        raise HTTPException(404, "No data available")
    # return broker.microgrids[name]
    return broker.history[name][-1]


@app.get("/microgrids/{name}/history")
def get_history(name: str, limit: int = 100):
    if name not in broker.history:
        raise HTTPException(404, "Microgrid not found")
    history = list(broker.history[name])
    return {"data": history[-limit:] if limit else history}


@app.put("/microgrids/{name}/storage/min_soc")  # TODO experimental
def set_min_soc(name: str, value: dict[str, float]):
    broker.add_command(
        {
            "type": "set_parameter",
            "microgrid": name,
            "parameter": "storage:min_soc",
            "value": value["min_soc"],
        }
    )
    return {"status": "command queued"}


# Prometheus metrics endpoint
@app.get("/metrics")
def get_prometheus_metrics():
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


def run_broker(port: int = 8700):
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
