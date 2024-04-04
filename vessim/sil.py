"""Vessim Software-in-the-Loop (SiL) components.

This module is still experimental, the public API might change at any time.
"""

from __future__ import annotations

import multiprocessing
from queue import Empty as QueueEmpty
from collections import defaultdict
from datetime import datetime, timedelta
from threading import Thread
from time import sleep
from typing import Any, Optional, Callable, Iterable

import pandas as pd
import requests
import uvicorn
from fastapi import FastAPI
from loguru import logger
from requests.auth import HTTPBasicAuth

from vessim.cosim import Controller, Microgrid
from vessim.signal import Signal
from vessim._util import DatetimeLike


def _iterate_queue(q: multiprocessing.Queue, timeout: Optional[float] = None) -> Iterable[Any]:
    blocking = timeout is not None
    while True:
        try:
            yield q.get(blocking, timeout)
        except QueueEmpty:
            break


class Broker:
    def __init__(self, queue_size: int = 0):
        # Note: Any objects put onto queues are automatically pickled and depickled when retrieved.
        self._outgoing_events_queue: Optional[multiprocessing.Queue] = multiprocessing.Queue(
            maxsize=queue_size
        )
        self._incoming_data_queue: Optional[multiprocessing.Queue] = multiprocessing.Queue(
            maxsize=queue_size
        )
        self._microgrid: Optional[Microgrid] = None
        self._actor_infos: Optional[dict] = None
        self._p_delta: Optional[float] = None

    def get_microgrid(self) -> Microgrid:
        self._process_incoming_data()
        assert self._microgrid is not None
        return self._microgrid

    def get_actor(self, actor: str) -> dict:
        self._process_incoming_data()
        assert self._actor_infos is not None
        return self._actor_infos

    def get_p_delta(self) -> float:
        self._process_incoming_data()
        assert self._p_delta is not None
        return self._p_delta

    def set_event(self, category: str, value: Any) -> None:
        if self._outgoing_events_queue is not None:
            self._outgoing_events_queue.put(
                {
                    "category": category,
                    "time": datetime.now(),
                    "value": value,
                }
            )

    def _add_microgrid_data(self, time: datetime, data: dict) -> None:
        if self._incoming_data_queue is not None:
            self._incoming_data_queue.put((time, data))

    def _consume_events(self) -> Iterable[dict]:
        if self._outgoing_events_queue is not None:
            yield from _iterate_queue(self._outgoing_events_queue)

    # TODO-now note that this should really be run periodically
    def _process_incoming_data(self) -> None:
        if self._incoming_data_queue is not None:
            for time, data in _iterate_queue(self._incoming_data_queue):
                self._microgrid = data.pop("microgrid", self._microgrid)
                self._actor_infos = data.pop("actor_infos", self._actor_infos)
                self._p_delta = data.pop("p_delta", self._p_delta)

    def _finalize(self) -> None:
        assert self._outgoing_events_queue is not None
        self._outgoing_events_queue.close()
        self._outgoing_events_queue = None
        assert self._incoming_data_queue is not None
        self._incoming_data_queue.close()
        self._incoming_data_queue = None


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
        **kwargs,
    ):
        super().__init__(step_size=step_size)
        self.api_routes = api_routes
        self.grid_signals = grid_signals
        self.request_collectors = request_collectors if request_collectors is not None else {}
        self.api_host = api_host
        self.api_port = api_port
        self.request_collector_interval = request_collector_interval
        self.kwargs = kwargs
        self.broker = Broker()

        self.microgrid: Optional[Microgrid] = None

    def start(self, microgrid: Microgrid) -> None:
        self.microgrid = microgrid
        name = f"Vessim API for microgrid {id(self.microgrid)}"

        multiprocessing.Process(
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
        self.broker._add_microgrid_data(
            time,
            {
                "microgrid": self.microgrid,
                "actor_infos": actor_infos,
                "p_delta": p_delta,
            },
        )

    def finalize(self) -> None:
        self.broker._finalize()

    def _collect_set_requests_loop(self):
        while True:
            events_by_category = defaultdict(dict)
            for event in self.broker._consume_events():
                events_by_category[event["category"]][event["time"]] = event["value"]
            for category, events in events_by_category.items():
                self.request_collectors[category](
                    events=events_by_category[category],
                    microgrid=self.microgrid,
                    kwargs=self.kwargs,
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
    broker._finalize()


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
