"""Shed dependent jobs under an import limit, protecting the jobs others need.

python examples/criticality_aware_shedding.py
python -m vessim view results/criticality-aware-shedding

The demand-response example treats every job as equally safe to pause. Here the
jobs depend on each other. An edge (a, b) means job a needs job b. A paused job
draws no power, and running jobs that lose a dependency keep drawing power
without doing useful work:

- In batch pipelines a stage stalls when a stage it reads from is paused.
- In a request-serving application an endpoint is down when any service on its
  call tree is paused. A running service is useful only while it serves an
  endpoint that is up.

Count-based shedding pauses jobs in reverse admission order until demand fits.
It stands in for demand_response.py, which only lowers a count of identical jobs.

Dependency-criticality shedding pauses jobs in ascending order of a criticality
score. Before each pick it first pauses any running job that earlier pauses left
idle, since that job draws power for nothing. The score is
alpha * centrality + beta * demand entropy + gamma * declared criticality, the
Centrality-Entropy Index (P. Pokharel, FTC 2026). Jobs that nothing else needs
rank low, and shared dependencies and operator-declared critical jobs rank high.
The example uses alpha = 0.40 and gamma = 0.25, and beta defaults to 0: how
variable a job's load is says nothing about who depends on it.

The site imports at most a notified limit, announced one step ahead. Job demand
is forecast as its current draw, so a rising load or falling solar output can
still exceed the limit. A second connection supplies the excess and records it.
Job sizes, load shapes, and limit events are illustrative.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

from _common import fresh_output, write_study

import vessim as vs

DATASETS = Path(__file__).resolve().parents[1] / "datasets"
STEP = 300
BASE_LOAD = 400.0  # W, as in demand_response.py
IDLE_SHARE = 0.3  # share of a job's peak power drawn at zero utilization


def pipelines(n_jobs: int, seed: int = 0) -> nx.DiGraph:
    """Independent batch pipelines. Pipeline 0 is declared critical."""
    count = max(2, round(n_jobs / 5))
    g = nx.DiGraph(kind="batch")
    for p, stages in enumerate(np.array_split(np.arange(n_jobs), count)):
        names = [f"pipe{p}-stage{s}" for s in range(len(stages))]
        g.add_nodes_from(names, critical=1.0 if p == 0 else 0.0)
        g.add_edges_from(zip(names[1:], names[:-1]))  # each stage reads the previous one
    return g


def microservices(n_jobs: int, seed: int = 0) -> nx.DiGraph:
    """A frontend calling API handlers, internal services, and shared stores."""
    rng = np.random.default_rng(seed)
    rest = n_jobs - 1
    n_api, n_svc = max(2, round(0.3 * rest)), max(1, round(0.3 * rest))
    api = [f"api{i}" for i in range(n_api)]
    svc = [f"svc{i}" for i in range(n_svc)]
    store = [f"store{i}" for i in range(max(1, rest - n_api - n_svc))]
    popularity = 1 / np.arange(1, len(store) + 1)  # a few stores are shared widely

    def pick(names, k, weights=None):
        p = None if weights is None else weights / weights.sum()
        return [str(n) for n in rng.choice(names, size=min(k, len(names)), replace=False, p=p)]

    def stores(k):
        return pick(store, k, popularity)

    g = nx.DiGraph(kind="service")
    g.add_node("frontend", critical=1.0)
    g.add_nodes_from(api + svc + store, critical=0.0)
    for a in api:
        g.add_edge("frontend", a)
        g.add_edges_from((a, s) for s in pick(svc, rng.integers(1, 3)))
        g.add_edges_from((a, s) for s in stores(1))
    for s in svc:
        if g.in_degree(s) == 0:
            g.add_edge(pick(api, 1)[0], s)
        g.add_edges_from((s, t) for t in stores(rng.integers(1, 3)))
    for t in store:
        if g.in_degree(t) == 0:
            g.add_edge(pick(svc, 1)[0], t)
    g.graph["endpoints"] = {a: frozenset({"frontend", a} | nx.descendants(g, a)) for a in api}
    return g


def job_load(graph: nx.DiGraph, steps: int, seed: int = 0):
    """Peak power and a utilization series per job, drawn from the bundled load traces."""
    rng = np.random.default_rng(seed)
    traces = pd.read_csv(DATASETS / "load_example.csv", index_col="time")
    hours = np.arange(steps + 1) * STEP / 3600
    peak, util = {}, {}
    for job in graph:
        column = traces[rng.choice(traces.columns)]
        offset = rng.integers(0, len(column) - int(hours[-1]) - 2)
        series = np.interp(hours + offset, np.arange(len(column)), column.to_numpy())
        util[job] = np.clip(series * rng.normal(1.0, 0.05, series.size), 0.0, 1.0)
        peak[job] = float(np.clip(rng.lognormal(np.log(100), 0.5), 30, 400))
    return peak, util


def pagerank(graph: nx.DiGraph, damping: float = 0.85, iterations: int = 100) -> dict:
    """Power-iteration PageRank, so the example needs no SciPy."""
    nodes = list(graph)
    adjacency = nx.to_numpy_array(graph, nodelist=nodes)
    out = adjacency.sum(axis=1, keepdims=True)
    # Jobs that need nothing spread their rank evenly, as in networkx.pagerank.
    walk = np.where(out > 0, adjacency / np.where(out > 0, out, 1), 1 / len(nodes))
    rank = np.full(len(nodes), 1 / len(nodes))
    for _ in range(iterations):
        rank = damping * rank @ walk + (1 - damping) / len(nodes)
    return dict(zip(nodes, rank))


def composite_centrality(graph: nx.DiGraph) -> dict[str, float]:
    """PageRank, betweenness, degree, and closeness on the needs graph, scaled to [0, 1]."""
    pr = pagerank(graph)
    bw = nx.betweenness_centrality(graph)
    dg = nx.degree_centrality(graph)
    cl = nx.closeness_centrality(graph)  # inward distance: jobs many others reach
    score = {n: 0.35 * pr[n] + 0.30 * bw[n] + 0.20 * dg[n] + 0.15 * cl[n] for n in graph}
    top = max(score.values())
    return {n: v / top for n, v in score.items()}


def demand_entropy(window: np.ndarray, bins: int = 10) -> float:
    """Shannon entropy of utilization over 10 bins in [0, 1], scaled to [0, 1]."""
    counts, _ = np.histogram(window, bins=bins, range=(0.0, 1.0))
    p = counts[counts > 0] / counts.sum()
    return float(-(p * np.log2(p)).sum() / np.log2(bins))


class Datacenter(vs.Consumer):
    """A base load plus jobs whose dependencies form a directed graph."""

    def __init__(self, name, graph, peak, util, base=BASE_LOAD):
        super().__init__(name, signal=base)
        self.graph, self.peak, self.util, self.base = graph, peak, util, base
        self.paused: frozenset = frozenset()
        self.needed_by = {job: nx.ancestors(graph, job) for job in graph}
        self.endpoints = graph.graph.get("endpoints", {})
        self.k = 0

    def demand(self, k):
        share = IDLE_SHARE + (1 - IDLE_SHARE) * np.array([self.util[j][k] for j in self.graph])
        return dict(zip(self.graph, share * np.array([self.peak[j] for j in self.graph])))

    def mean_demand(self, steps):
        return self.base + np.mean([sum(self.demand(k).values()) for k in range(steps)])

    def useful(self, paused):
        """Running jobs that make progress while the given jobs are paused."""
        running = set(self.graph) - paused
        if self.graph.graph["kind"] == "service":
            up = [req for req in self.endpoints.values() if not req & paused]
            return running & set().union(*up)
        stalled = set().union(*(self.needed_by[j] for j in paused))
        return running - stalled

    def sample(self, elapsed):
        seconds = elapsed.total_seconds() if hasattr(elapsed, "total_seconds") else elapsed
        self.k = int(seconds // STEP)
        demand, paused = self.demand(self.k), self.paused
        running = [j for j in self.graph if j not in paused]
        useful = self.useful(paused)
        power = -(self.base + sum(demand[j] for j in running))
        served = sum(1 for req in self.endpoints.values() if not req & paused)
        return power, {
            "power": power,
            # Sum in graph order: set order varies between processes.
            "useful_power": sum(demand[j] for j in self.graph if j in useful),
            "broken_power": sum(demand[j] for j in running if j not in useful),
            "paused_power": sum(demand[j] for j in self.graph if j in paused),
            "paused_jobs": len(paused),
            "broken_jobs": len(running) - len(useful),
            "critical_paused": sum(1 for j in paused if self.graph.nodes[j]["critical"] > 0),
            "endpoints_up": served,
        }


class CountShedding:
    """Pause jobs in reverse admission order until demand fits."""

    def __init__(self, admission_order):
        self.order = list(reversed(admission_order))

    def ranking(self, datacenter):
        return self.order


def with_closure(datacenter, order):
    """Yield jobs in order, first pausing any job the earlier pauses left idle.

    A running job is idle when it can no longer do useful work because something
    it needs is paused. Pausing it saves its power without losing any work.
    """
    paused = set()
    for job in order:
        if job in paused:
            continue
        useful = datacenter.useful(frozenset(paused))
        for idle in [j for j in datacenter.graph if j not in paused and j not in useful]:
            paused.add(idle)
            yield idle
        if job not in paused:
            paused.add(job)
            yield job


class CriticalityShedding:
    """Pause the lowest-scoring jobs, each after any jobs earlier pauses left idle."""

    def __init__(self, graph, alpha=0.40, beta=0.0, gamma=0.25, window=288, closure=True):
        self.weights = (alpha, beta, gamma)
        self.window = window
        self.closure = closure
        self.centrality = composite_centrality(graph)
        self.declared = {j: graph.nodes[j]["critical"] for j in graph}

    def index(self, datacenter):
        alpha, beta, gamma = self.weights
        lo, hi = max(0, datacenter.k - self.window + 1), datacenter.k + 1
        score = {
            j: alpha * self.centrality[j] + gamma * self.declared[j] for j in datacenter.graph
        }
        if beta:  # the entropy term needs a histogram per job and step
            for j in score:
                score[j] += beta * demand_entropy(datacenter.util[j][lo:hi])
        return score

    def ranking(self, datacenter):
        score = self.index(datacenter)
        order = sorted(score, key=lambda j: (score[j], j))
        return with_closure(datacenter, order) if self.closure else order


def select_paused(ranking, demand, budget):
    """Pause jobs in ranking order until the remaining demand fits the budget."""
    load, paused = sum(demand.values()), set()
    for job in ranking:
        if load <= budget:
            break
        paused.add(job)
        load -= demand[job]
    return frozenset(paused)


class Shedding(vs.Controller):
    """Fit the next step's job demand under the announced import limit."""

    def __init__(self, datacenter, policy, grid, microgrid="site"):
        self.datacenter = datacenter
        self.policy = policy
        self.grid = grid
        self.microgrid = microgrid

    def step(self, now, states):
        site = states[self.microgrid]
        limit = site["grid_signals"]["next_import_limit"]
        solar = site["actor_states"]["solar"]["power"]
        dc = self.datacenter
        budget = limit + solar - dc.base
        dc.paused = select_paused(self.policy.ranking(dc), dc.demand(dc.k), budget)
        self.grid.max_import = limit


class StateEnergy(vs.Metric):
    """Integrate one power field of the datacenter's state, in Wh."""

    def __init__(self, field, description):
        super().__init__("Wh", microgrid="site", description=description)
        self.field = field

    def step(self, now, states, duration):
        self.value += states["site"]["actor_states"]["datacenter"][self.field] * duration / 3600


class OverflowImport(vs.Metric):
    """Energy imported above the notified limit, in Wh."""

    def __init__(self):
        super().__init__("Wh", microgrid="site", description="Import above the notified limit")

    def step(self, now, states, duration):
        power = states["site"]["dispatch_states"]["overflow"]["current_power"]
        self.value += max(0.0, -power) * duration / 3600


def limit_series(steps, events, limit, unconstrained):
    """Per-step import limit in W: `limit` inside (start_h, end_h) daily windows."""
    hours = (np.arange(steps + 2) * STEP / 3600) % 24
    inside = np.zeros(hours.size, dtype=bool)
    for start, end in events:
        inside |= (hours >= start) & (hours < end)
    return np.where(inside, limit, unconstrained)


def simulate(
    output,
    run_id,
    graph,
    peak,
    util,
    policy,
    limits,
    *,
    solar_w=1500,
    parameters=None,
    timeseries=True,
):
    """Run one scenario with Berlin solar. limits[k] is the import limit for step k."""
    steps = len(limits) - 2
    seconds = np.arange(steps + 1) * STEP
    carbon = pd.read_csv(DATASETS / "watttime_example.csv").iloc[: steps + 1, 1].to_numpy()
    datacenter = Datacenter("datacenter", graph, peak, util)
    grid = vs.GridConnection("grid", max_import=float(limits[0]))
    with vs.Environment("2026-01-01", step_size=STEP) as env:
        env.add_microgrid(
            name="site",
            actors=[
                datacenter,
                vs.Producer(
                    "solar",
                    signal=vs.Trace.from_csv(
                        DATASETS / "solar_example.csv", column="Berlin", scale=solar_w
                    ),
                ),
            ],
            dispatchables=[grid, vs.GridConnection("overflow", max_export=0)],
            grid_signals={
                "next_import_limit": vs.Trace(pd.Series(limits[1 : steps + 2], index=seconds)),
                # WattTime MOER in lbs/MWh, converted to kgCO2/kWh
                "carbon": vs.Trace(pd.Series(carbon * 0.45359237 / 1000, index=seconds)),
            },
        )
        env.add_controller(Shedding(datacenter, policy, grid))
        recorder = env.add_controller(
            vs.Recorder(
                output,
                run_id=run_id,
                timeseries=timeseries,
                parameters=parameters or {},
                custom_metrics={
                    "useful_energy": StateEnergy("useful_power", "Job energy doing useful work"),
                    "broken_energy": StateEnergy(
                        "broken_power", "Job energy drawn while a dependency is paused"
                    ),
                    "paused_energy": StateEnergy("paused_power", "Job demand paused and deferred"),
                    "overflow_import": OverflowImport(),
                    "grid_emissions": vs.GridImportEmissions("site", "carbon"),
                },
            )
        )
        env.run(steps * STEP)
    return recorder.result


WORKLOADS = {"pipelines": pipelines, "microservices": microservices}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("results/criticality-aware-shedding"))
    parser.add_argument("--jobs", type=int, default=15)
    parser.add_argument("--days", type=int, default=2)
    parser.add_argument("--cap", type=float, default=0.7, help="limit as a share of mean demand")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-timeseries", action="store_true")
    args = parser.parse_args()
    if args.jobs < 5 or not 1 <= args.days <= 20 or not 0 < args.cap <= 1 or args.seed < 0:
        parser.error("needs jobs >= 5, 1 <= days <= 20, 0 < cap <= 1, nonnegative seed")
    fresh_output(args.output)
    steps = args.days * 86400 // STEP
    groups, rows = [], []
    for workload, build in WORKLOADS.items():
        graph = build(args.jobs, args.seed)
        peak, util = job_load(graph, steps, args.seed)
        mean_demand = Datacenter("probe", graph, peak, util).mean_demand(steps)
        limits = limit_series(steps, [(17, 21)], args.cap * mean_demand, 10 * mean_demand)
        admitted = [str(j) for j in np.random.default_rng(args.seed).permutation(list(graph))]
        policies = {
            "count": CountShedding(admitted),
            "criticality": CriticalityShedding(graph),
        }
        for name, policy in policies.items():
            run_id = f"{workload}-{name}"
            result = simulate(
                args.output / run_id,
                run_id,
                graph,
                peak,
                util,
                policy,
                limits,
                parameters={
                    "workload": workload,
                    "policy": name,
                    "jobs": args.jobs,
                    "cap": args.cap,
                    "seed": args.seed,
                },
                timeseries=not args.no_timeseries,
            )
            groups.append((run_id, f"{workload}, {name}", [run_id]))
            rows.append((workload, name, result.metrics["microgrids"]["site"]))
    write_study(
        args.output,
        "criticality-aware-shedding",
        "Dependency-aware load shedding",
        groups,
        description=(
            "The grid limits imports each evening, so the datacenter pauses jobs. "
            "Count-based shedding pauses the most recently admitted jobs. Criticality-aware "
            "shedding pauses the jobs nothing else needs, each time after any jobs that "
            "earlier pauses left with nothing useful to do. Compare the energy each keeps "
            "doing useful work and the energy lost to jobs whose dependencies were paused."
        ),
    )
    header = ("workload", "policy", "useful", "broken", "paused", "overflow")
    print("{:<14} {:<12} {:>10} {:>10} {:>10} {:>10}".format(*header))
    for workload, name, m in rows:
        kwh = [m[k] / 1000 for k in ("useful_energy", "broken_energy", "paused_energy")]
        kwh.append(m["overflow_import"] / 1000)
        print(f"{workload:<14} {name:<12} " + " ".join(f"{v:>6.2f} kWh" for v in kwh))
    print(f"View: python -m vessim view {args.output}")


if __name__ == "__main__":
    main()
