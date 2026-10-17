import socket
from threading import Event

import pytest

import vessim as vs


def test_signal_worker_stops_after_run_and_after_interruption():
    for interrupted in (False, True):
        fetched = Event()

        class Signal(vs.SilSignal):
            def _fetch_current_value(self):
                fetched.set()
                return 123

        signal = Signal(update_interval=60, timeout=0.5)
        assert fetched.wait(1)
        env = vs.Environment.live()
        env.add_microgrid([vs.Actor("live", signal)], dispatchables=[vs.GridConnection()])

        class Finish(vs.Controller):
            def step(self, now, states):
                if interrupted:
                    raise KeyboardInterrupt

        env.add_controller(Finish())
        if interrupted:
            with pytest.raises(KeyboardInterrupt):
                env.run(0.01)
        else:
            assert env.run(0.01).states["microgrid_0"]["p_delta"] == 123
        assert not signal._thread.is_alive()
        signal.finalize()  # Idempotent even when shared with another owner.


def test_live_broker_round_trip_and_cleanup():
    pytest.importorskip("fastapi")
    requests = pytest.importorskip("requests")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = vs.Environment.live()
    signal = vs.StaticSignal(100)
    env.add_microgrid([vs.Actor("load", signal)], name="grid", dispatchables=[vs.GridConnection()])
    api = env.add_controller(vs.Api(broker_port=port))
    observed = []

    class Client(vs.Controller):
        def step(self, now, states):
            response = requests.get(f"{api.broker_url}/microgrids/grid", timeout=1)
            response.raise_for_status()
            observed.append(response.json())

    env.add_controller(Client())
    env.run(0.01)
    assert len(observed) == 1
    assert not api.broker_process.is_alive()


def test_failed_prometheus_setup_starts_no_worker(monkeypatch):
    requests = pytest.importorskip("requests")
    import threading

    def failed(*args, **kwargs):
        raise requests.ConnectionError("unavailable")

    monkeypatch.setattr(requests, "get", failed)
    before = {id(t) for t in threading.enumerate()}
    with pytest.raises(ConnectionError, match="Could not connect"):
        vs.PrometheusSignal("http://localhost:1", "up", timeout=0.1)
    assert {id(t) for t in threading.enumerate()} == before
