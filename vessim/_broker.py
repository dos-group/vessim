from datetime import datetime
import threading
from collections import defaultdict, deque

from fastapi import FastAPI, HTTPException
import uvicorn


class DataBroker:
    def __init__(self):
        self.microgrids: dict[str, dict] = {}
        self.history: dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.commands: list[dict] = []
        self.lock = threading.Lock()
        self.status = "stopped"
        self.sim_start_time = None

    def add_microgrid(self, name: str, config: dict[str, any]):
        with self.lock:
            self.microgrids[name] = config

    def push_data(self, microgrid_name: str, data: dict[str, any]):
        with self.lock:
            self.history[microgrid_name].append(data)
            self.status = "running"
            if not self.sim_start_time:
                self.sim_start_time = datetime.now()

    def get_commands(self) -> list[dict]:
        with self.lock:
            commands = self.commands.copy()
            self.commands.clear()
            return commands

    def add_command(self, command: dict[str, any]):
        with self.lock:
            self.commands.append(command)


broker = DataBroker()
app = FastAPI()

# Simulation-facing API
@app.post("/internal/data/{microgrid_name}")
def push_data(microgrid_name: str, data: dict[str, any]):
    broker.push_data(microgrid_name, data)
    return {"status": "ok"}

@app.post("/internal/microgrids/{name}")
def register_microgrid(name: str, config: dict[str, any]):
    broker.add_microgrid(name, config)
    return {"status": "ok"}

@app.get("/internal/commands")
def get_commands():
    return {"commands": broker.get_commands()}

# User-facing API
@app.get("/api/microgrids")
def list_microgrids():
    with broker.lock:
        return {
            "microgrids": list(broker.microgrids.keys()),
            "count": len(broker.microgrids)
        }

@app.get("/api/microgrids/{name}")
def get_microgrid_config(name: str):
    with broker.lock:
        if name not in broker.microgrids:
            raise HTTPException(404, "Microgrid not found")
        return broker.microgrids[name]

@app.get("/api/microgrids/{name}/latest")
def get_latest_data(name: str):
    with broker.lock:
        if name not in broker.history or not broker.history[name]:
            raise HTTPException(404, "No data available")
        return broker.history[name][-1]

@app.get("/api/microgrids/{name}/history")
def get_history(name: str, limit: int = 100):
    with broker.lock:
        if name not in broker.history:
            raise HTTPException(404, "Microgrid not found")
        history = list(broker.history[name])
        return {"data": history[-limit:] if limit else history}

@app.get("/api/status")
def get_status():
    with broker.lock:
        return {
            "status": broker.status,
            "sim_start_time": broker.sim_start_time.isoformat() if broker.sim_start_time else None,
            "microgrids": list(broker.microgrids.keys())
        }

@app.put("/api/microgrids/{name}/storage/min_soc")
def set_min_soc(name: str, value: dict[str, float]):
    broker.add_command({
        "type": "set_parameter",
        "microgrid": name,
        "parameter": "storage:min_soc",
        "value": value["min_soc"]
    })
    return {"status": "command queued"}


def run_broker(port: int = 8502):
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")