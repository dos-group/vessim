"""Check the dependency semantics and shedding policies of the criticality example."""

import importlib
from pathlib import Path

import numpy as np
import pytest

nx = pytest.importorskip("networkx")


@pytest.fixture
def shedding(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "examples"))
    return importlib.import_module("criticality_aware_shedding")


def flat_datacenter(module, graph, power=100.0, steps=10):
    peak = {job: power for job in graph}
    util = {job: np.ones(steps + 1) for job in graph}
    return module.Datacenter("datacenter", graph, peak, util)


def test_select_paused_follows_ranking_and_stops_when_demand_fits(shedding):
    demand = {"a": 50.0, "b": 30.0, "c": 20.0}
    assert shedding.select_paused(["a", "b", "c"], demand, 100) == frozenset()
    assert shedding.select_paused(["c", "b", "a"], demand, 60) == {"c", "b"}
    assert shedding.select_paused(["a", "b", "c"], demand, 60) == {"a"}
    assert shedding.select_paused(["a", "b", "c"], demand, -1) == {"a", "b", "c"}


def test_paused_batch_stage_stalls_every_stage_that_reads_it(shedding):
    graph = nx.DiGraph(kind="batch")
    graph.add_nodes_from(["s0", "s1", "s2", "other"], critical=0.0)
    graph.add_edges_from([("s1", "s0"), ("s2", "s1")])  # s2 reads s1 reads s0
    dc = flat_datacenter(shedding, graph)
    assert dc.useful(frozenset({"s2"})) == {"s0", "s1", "other"}
    assert dc.useful(frozenset({"s0"})) == {"other"}
    dc.paused = frozenset({"s0"})
    power, state = dc.sample(0)
    assert power == pytest.approx(-(shedding.BASE_LOAD + 300))
    assert state["broken_power"] == pytest.approx(200)
    assert state["useful_power"] == pytest.approx(100)
    assert state["paused_power"] == pytest.approx(100)
    assert state["broken_jobs"] == 2


def test_endpoint_is_down_when_any_service_on_its_call_tree_is_paused(shedding):
    graph = nx.DiGraph(kind="service")
    graph.add_nodes_from(["frontend", "a", "b", "db", "cache"], critical=0.0)
    graph.add_edges_from([("frontend", "a"), ("frontend", "b"), ("a", "db"), ("b", "cache")])
    graph.graph["endpoints"] = {
        "a": frozenset({"frontend", "a", "db"}),
        "b": frozenset({"frontend", "b", "cache"}),
    }
    dc = flat_datacenter(shedding, graph)
    # Pausing db takes endpoint a down. Service a keeps running without serving anything.
    assert dc.useful(frozenset({"db"})) == {"frontend", "b", "cache"}
    dc.paused = frozenset({"frontend"})
    _, state = dc.sample(0)
    assert state["endpoints_up"] == 0
    assert state["useful_power"] == 0
    assert state["broken_power"] == pytest.approx(400)


def test_criticality_index_protects_shared_and_declared_jobs(shedding):
    graph = shedding.microservices(20, seed=3)
    dc = flat_datacenter(shedding, graph)
    policy = shedding.CriticalityShedding(graph, closure=False)
    order = policy.ranking(dc)
    assert order[-1] == "frontend"  # declared critical
    callers = {store: graph.in_degree(store) for store in graph if store.startswith("store")}
    widely, rarely = max(callers, key=callers.get), min(callers, key=callers.get)
    assert order.index(widely) > order.index(rarely)
    assert sorted(order) == sorted(graph)


def test_entropy_term_ranks_bursty_load_above_steady_load_when_enabled(shedding):
    graph = nx.DiGraph(kind="batch")
    graph.add_nodes_from(["steady", "bursty"], critical=0.0)
    steps = 10
    peak = {"steady": 100.0, "bursty": 100.0}
    util = {"steady": np.full(steps + 1, 0.5), "bursty": np.resize([0.0, 1.0], steps + 1)}
    dc = shedding.Datacenter("datacenter", graph, peak, util)
    dc.k = steps
    off = shedding.CriticalityShedding(graph, closure=False).index(dc)
    assert off["steady"] == off["bursty"]
    on = shedding.CriticalityShedding(graph, beta=0.35, closure=False)
    assert on.index(dc)["bursty"] > on.index(dc)["steady"]
    assert on.ranking(dc) == ["steady", "bursty"]


def test_closure_pauses_jobs_left_idle_before_the_next_pick(shedding):
    graph = nx.DiGraph(kind="batch")
    graph.add_nodes_from(["s0", "s1", "s2", "other"], critical=0.0)
    graph.add_edges_from([("s1", "s0"), ("s2", "s1")])  # s2 reads s1 reads s0
    dc = flat_datacenter(shedding, graph)
    order = list(shedding.with_closure(dc, ["s0", "other", "s1", "s2"]))
    assert order == ["s0", "s1", "s2", "other"]
    # Pausing a job nothing needs leaves nothing idle.
    assert list(shedding.with_closure(dc, ["s2", "other", "s1", "s0"])) == [
        "s2",
        "other",
        "s1",
        "s0",
    ]


def test_closure_pauses_services_whose_endpoints_are_all_down(shedding):
    graph = nx.DiGraph(kind="service")
    graph.add_nodes_from(["frontend", "a", "b", "db", "cache"], critical=0.0)
    graph.add_edges_from([("frontend", "a"), ("frontend", "b"), ("a", "db"), ("b", "cache")])
    graph.graph["endpoints"] = {
        "a": frozenset({"frontend", "a", "db"}),
        "b": frozenset({"frontend", "b", "cache"}),
    }
    dc = flat_datacenter(shedding, graph)
    order = list(shedding.with_closure(dc, ["db", "cache", "frontend", "a", "b"]))
    # Pausing db takes endpoint a down, so a is idle. The frontend still serves b.
    assert order[:2] == ["db", "a"]
    # Pausing cache takes the last endpoint down, so the frontend and b are idle too.
    assert order[2:] == ["cache", "frontend", "b"]
    demand = dc.demand(0)
    assert shedding.select_paused(
        shedding.with_closure(dc, ["db", "cache", "frontend", "a", "b"]), demand, 300
    ) == {"db", "a"}


def test_criticality_shedding_applies_closure_by_default(shedding):
    graph = shedding.pipelines(10, seed=1)
    dc = flat_datacenter(shedding, graph)
    with_closure = list(shedding.CriticalityShedding(graph).ranking(dc))
    without = shedding.CriticalityShedding(graph, closure=False).ranking(dc)
    assert sorted(with_closure) == sorted(without) == sorted(graph)
    assert with_closure != without
    # Before every ranked pick of a useful job, no running job is left idle.
    for k, job in enumerate(with_closure):
        paused = frozenset(with_closure[:k])
        useful = dc.useful(paused)
        if job in useful:
            assert useful == set(graph) - paused


def test_count_shedding_pauses_latest_admitted_first(shedding):
    policy = shedding.CountShedding(["first", "second", "third"])
    assert policy.ranking(None) == ["third", "second", "first"]


def test_job_energy_is_conserved_and_limits_hold_without_forecast_error(shedding, tmp_path):
    graph = shedding.pipelines(10, seed=1)
    steps = 288
    dc = flat_datacenter(shedding, graph, steps=steps)
    limits = shedding.limit_series(steps, [(0, 24)], 700.0, 700.0)
    result = shedding.simulate(
        tmp_path / "run",
        "run",
        graph,
        dc.peak,
        dc.util,
        shedding.CriticalityShedding(graph),
        limits,
        solar_w=0,
        timeseries=False,
    )
    site = result.metrics["microgrids"]["site"]
    jobs_wh = 10 * 100 * 24  # ten 100 W jobs for one day
    total = site["useful_energy"] + site["broken_energy"] + site["paused_energy"]
    assert total == pytest.approx(jobs_wh)
    # The controller first acts after tick zero, so only the first step exceeds the limit.
    # Constant demand and no solar make the persistence forecast exact afterwards.
    first_step = (shedding.BASE_LOAD + 1000 - 700) * shedding.STEP / 3600
    assert site["overflow_import"] == pytest.approx(first_step)
