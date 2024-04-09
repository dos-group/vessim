"""Vessim Software-in-the-Loop (SiL) components.

This module is still experimental, the public API might change at any time.
"""

from __future__ import annotations

from multiprocessing import Process, Pipe
from multiprocessing.connection import Connection
from collections import defaultdict
from datetime import datetime, timedelta
from threading import Thread
from time import sleep
from typing import Any, Optional, Callable

import pandas as pd
import requests
import uvicorn
from fastapi import FastAPI
from loguru import logger
from requests.auth import HTTPBasicAuth

from vessim.cosim import Controller, Microgrid
from vessim.signal import Signal
from vessim._util import DatetimeLike


class Broker:
    def __init__(self, data_pipe_out: Connection, events_pipe_in: Connection):
        self._data_pipe_out = data_pipe_out
        self._events_pipe_in = events_pipe_in
        self._microgrid_ts: dict[DatetimeLike, Microgrid] = {}
        self._actor_infos_ts: dict[DatetimeLike, dict] = {}
        self._p_delta_ts: dict[DatetimeLike, float] = {}
        self._microgrid: Optional[Microgrid] = None
        self._actor_infos: dict = {}
        self._p_delta: float = 0
        Thread(target=self._recv_data, daemon=True).start()

    def _recv_data(self) -> None:
        while True:
            time, data = self._data_pipe_out.recv()
            self._microgrid_ts[time] = self._microgrid = data["microgrid"]
            self._actor_infos_ts[time] = self._actor_infos = data["actor_infos"]
            self._p_delta_ts[time] = self._p_delta = data["p_delta"]

    def get_microgrid(self) -> Microgrid | None:
        return self._microgrid

    def get_microgrid_ts(self) -> dict[DatetimeLike, Microgrid]:
        return self._microgrid_ts

    def get_actor(self, actor: str) -> dict:
        return self._actor_infos[actor]

    def get_actor_ts(self) -> dict[DatetimeLike, dict]:
        return self._actor_infos_ts

    def get_p_delta(self) -> float:
        return self._p_delta

    def get_p_delta_ts(self) -> dict[DatetimeLike, float]:
        return self._p_delta_ts

    def set_event(self, category: str, value: Any) -> None:
        self._events_pipe_in.send(
            {
                "category": category,
                "time": datetime.now(),
                "value": value,
            }
        )


class SilController(Controller):
    def __init__(
        self,
        api_routes: Callable,
        grid_signals: Optional[list[Signal]] = None,  # TODO temporary fix
        request_collectors: Optional[dict[str, Callable]] = None,
        api_host: str = "127.0.0.1",
        api_port: int = 8000,
        request_collector_interval: float = 1,
        step_size: Optional[int] = None,
    ):
        super().__init__(step_size=step_size)
        self.api_routes = api_routes
        self.grid_signals = grid_signals
        self.request_collectors = request_collectors if request_collectors is not None else {}
        self.api_host = api_host
        self.api_port = api_port
        self.request_collector_interval = request_collector_interval
        self.microgrid: Optional[Microgrid] = None

        self.events_pipe_out, events_pipe_in = Pipe(duplex=False)
        data_pipe_out, self.data_pipe_in = Pipe(duplex=False)
        self.broker = Broker(data_pipe_out, events_pipe_in)

    def start(self, microgrid: Microgrid) -> None:
        self.microgrid = microgrid
        name = f"Vessim API for microgrid {id(self.microgrid)}"

        Process(
            target=_serve_api,
            name=name,
            daemon=True,
            kwargs=dict(
                api_routes=self.api_routes,
                api_host=self.api_host,
                api_port=self.api_port,
                broker=self.broker,
                grid_signals=self.grid_signals,
            ),
        ).start()
        logger.info(f"Started SiL Controller API server process '{name}'")

        Thread(target=self._collect_set_requests_loop, daemon=True).start()

    def step(self, time: datetime, p_delta: float, actor_infos: dict) -> None:
        assert self.microgrid is not None
        self.data_pipe_in.send(
            (
                time,
                {
                    "microgrid": self.microgrid,
                    "actor_infos": actor_infos,
                    "p_delta": p_delta,
                },
            )
        )

    def _collect_set_requests_loop(self):
        while True:
            events_by_category = defaultdict(dict)
            while self.events_pipe_out.poll():
                event = self.events_pipe_out.recv()
                events_by_category[event["category"]][event["time"]] = event["value"]
            for category, _ in events_by_category.items():
                self.request_collectors[category](
                    events=events_by_category[category],
                    microgrid=self.microgrid,
                )
            sleep(self.request_collector_interval)


def _serve_api(
    api_routes: Callable,
    api_host: str,
    api_port: int,
    broker: Broker,
    grid_signals: dict[str, Signal],
):
    app = FastAPI()
    api_routes(app, broker, grid_signals)
    config = uvicorn.Config(app=app, host=api_host, port=api_port, access_log=False)
    server = uvicorn.Server(config=config)
    server.run()


def get_latest_event(events: dict[datetime, Any]) -> Any:
    return events[max(events.keys())]


class WatttimeSignal(Signal):
    _URL = "https://api.watttime.org"

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.headers = {"Authorization": f"Bearer {self._login()}"}

    def at(
        self,
        dt: DatetimeLike,
        region: Optional[str] = None,
        signal_type: str = "co2_moer",
        **kwargs,
    ):
        if region is None:
            raise ValueError("Region needs to be specified.")
        dt = pd.to_datetime(dt)
        rsp = self._request(
            "/historical",
            params={
                "region": region,
                "start": (dt - timedelta(minutes=5)).isoformat(),
                "end": dt.isoformat(),
                "signal_type": signal_type,
            },
        )
        return rsp

    def _request(self, endpoint: str, params: dict):
        while True:
            rsp = requests.get(f"{self._URL}/v3{endpoint}", headers=self.headers, params=params)
            if rsp.status_code == 200:
                return rsp.json()["data"][0]["value"]
            if rsp.status_code == 400:
                return f"Error {rsp.status_code}: {rsp.json()}"
            elif rsp.status_code in [401, 403]:
                print("Renewing authorization with Watttime API.")
                self.headers["Authorization"] = f"Bearer {self._login()}"
            else:
                raise ValueError(f"Error {rsp.status_code}: {rsp}")

    def _login(self) -> str:
        # TODO reconnect if token is expired
        rsp = requests.get(f"{self._URL}/login", auth=HTTPBasicAuth(self.username, self.password))
        return rsp.json()["token"]
