import socket
from threading import Event

import pytest

import vessim as vs


def test_signal_worker_stops_after_run_and_after_interruption():
    for interrupted in (False, True):
        fetched = Event()

        class Signal(vs.LiveSignal):
            def _fetch_current_value(self):
                fetched.set()
                return 123

            def at(self, elapsed):
                assert fetched.wait(5)
                return super().at(elapsed)

        signal = Signal(update_interval=60, timeout=0.5)
        assert signal._thread is None
        assert not fetched.is_set()
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
    load = vs.Consumer("load", signal=100)
    env.add_microgrid([load], name="grid", dispatchables=[vs.GridConnection()])
    api = env.add_controller(vs.Api(broker_port=port))
    observed = []

    class Client(vs.Controller):
        def step(self, now, states):
            response = requests.get(f"{api.broker_url}/microgrids/grid", timeout=5)
            response.raise_for_status()
            observed.append(response.json())
            if len(observed) == 1:
                response = requests.put(
                    f"{api.broker_url}/microgrids/grid/actors/load/signal",
                    params={"value": 200},
                    timeout=5,
                )
                response.raise_for_status()
                assert response.json() == {"status": "command queued"}

    env.add_controller(Client())
    env.run(2.01)
    assert [row["actor_states"]["load"]["power"] for row in observed] == [-100, -100, -200]
    assert isinstance(load.signal, vs.StaticSignal)
    assert load.signal.at() == 200
    assert not api.broker_process.is_alive()


def test_failed_prometheus_setup_starts_no_worker(monkeypatch):
    requests = pytest.importorskip("requests")

    def failed(*args, **kwargs):
        raise requests.ConnectionError("unavailable")

    monkeypatch.setattr(requests, "get", failed)
    signal = vs.PrometheusSignal("http://localhost:1", "up", timeout=0.1)
    assert signal._thread is None
    env = vs.Environment.live()
    env.add_microgrid([vs.Consumer("load", signal=signal)], [vs.GridConnection()])
    with pytest.raises(ConnectionError, match="Could not connect"):
        env.run(0.01)
    assert signal._thread is None
    assert signal._stop.is_set()


def test_watttime_initialization_is_deferred_and_failure_is_cleaned_up(monkeypatch):
    pytest.importorskip("requests")
    initialized = []

    def failed_login(self):
        initialized.append(self)
        raise RuntimeError("login failed")

    monkeypatch.setattr(vs.WatttimeSignal, "_get_token", failed_login)
    signal = vs.WatttimeSignal("user", "password", location=(52, 13))
    assert initialized == []
    assert "location=(52, 13)" in repr(signal)
    env = vs.Environment.live()
    env.add_microgrid(
        [vs.Consumer("load", signal=100)], [vs.GridConnection()], grid_signals={"carbon": signal}
    )
    with pytest.raises(RuntimeError, match="login failed"):
        env.run(1)
    assert initialized == [signal]
    assert signal._thread is None
    assert signal._stop.is_set()


def test_closed_live_signal_cannot_contact_service_again(monkeypatch):
    pytest.importorskip("requests")
    calls = []
    monkeypatch.setattr(vs.PrometheusSignal, "_validate_connection", lambda self: calls.append(1))
    signal = vs.PrometheusSignal("http://localhost:1", "up")
    signal.finalize()
    with pytest.raises(RuntimeError, match="closed live signal"):
        signal.start()
    assert calls == []
