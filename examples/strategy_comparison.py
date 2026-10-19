"""Compare three illustrative Python policies under the same load and solar traces.

python examples/strategy_comparison.py --output results/strategy-comparison
python -m vessim view results/strategy-comparison

Synthetic one-day traces and equipment costs demonstrate the viewer, not an
investment or emissions forecast. Each policy receives identical inputs per seed.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from _common import fresh_output, write_study

import vessim as vs


class StudyPolicy(vs.DefaultDispatchPolicy):
    """Illustrative dispatch policies with deliberately different behavior."""

    def __init__(self, strategy: str):
        super().__init__()
        self.strategy = strategy

    def apply(self, p_delta, duration, dispatchables, grid_signals=None):
        signals = grid_signals or {}
        if self.strategy == "carbon_aware":
            self.charge_power = 350 if signals.get("carbon", 1) < 0.15 else 0
        super().apply(p_delta, duration, dispatchables, grid_signals)

    def state(self):
        return {**super().state(), "strategy": self.strategy}


def run_scenario(
    output: Path,
    run_id: str,
    capacity_wh: float,
    strategy: str,
    seed: int = 42,
    timeseries: bool = True,
) -> vs.ExperimentResult:
    """Execute one fresh simulation and return its canonical experiment record."""
    if strategy not in ("self_consumption", "peak_shaving", "carbon_aware"):
        raise ValueError(f"Unknown strategy: {strategy}")
    if (output / run_id).exists():
        raise FileExistsError(f"Preserving existing run: {output / run_id}")
    rng = np.random.default_rng(seed)
    seconds = np.arange(0, 86400, 300)
    hours = seconds / 3600
    solar = np.maximum(0, np.sin((hours - 6) * np.pi / 12)) * 3200
    load = 850 + 550 * np.exp(-(((hours - 19) / 3) ** 2)) + rng.uniform(0, 180, len(hours))
    carbon = 0.25 + 0.15 * np.cos((hours - 20) * np.pi / 12)
    price = np.where((hours >= 17) & (hours < 21), 0.40, 0.18)

    def trace(values):
        return vs.Trace(pd.Series(values, index=seconds))

    with vs.Environment("2026-01-01", step_size=300, name="Campus energy study") as env:
        env.add_microgrid(
            [
                vs.Producer("solar", signal=trace(solar)),
                vs.Consumer("servers", signal=trace(load)),
            ],
            dispatchables=(
                # Use up to 1 kW from the grid before discharging storage.
                # The overflow connection keeps demand served if storage runs out.
                [
                    vs.GridConnection("base_import", max_import=1000, max_export=0),
                    vs.SimpleBattery("battery", capacity_wh, initial_soc=0.5),
                    vs.GridConnection("overflow"),
                ]
                if strategy == "peak_shaving"
                else [
                    vs.SimpleBattery("battery", capacity_wh, initial_soc=0.5),
                    vs.GridConnection(),
                ]
            ),
            policy=StudyPolicy(strategy),
            name="campus",
            grid_signals={"carbon": trace(carbon), "price": trace(price)},
        )
        recorder = env.add_controller(
            vs.Recorder(
                output / run_id,
                run_id=run_id,
                timeseries=timeseries,
                parameters={
                    "strategy": strategy,
                    "battery_capacity_wh": capacity_wh,
                    "seed": seed,
                },
                custom_metrics={
                    "electricity_cost": vs.ElectricityImportCost("campus", "price"),
                    "grid_emissions": vs.GridImportEmissions("campus", "carbon"),
                },
            )
        )
        env.run(86400)
    result = recorder.result
    result.add_metric(
        "battery_capex",
        capacity_wh / 1000 * 400,
        "EUR",
        description="Illustrative installed battery cost",
        assumptions={"eur_per_kwh": 400, "source": "synthetic example"},
    )
    result.save(output / run_id / "experiment.json")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("results/strategy-comparison"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--scenarios", type=int, default=5)
    parser.add_argument("--capacity-wh", type=float, default=4000)
    parser.add_argument("--no-timeseries", action="store_true")
    args = parser.parse_args()
    if args.seed < 0 or args.scenarios < 1 or args.capacity_wh <= 0:
        parser.error("seed must be nonnegative, scenarios and capacity must be positive")
    fresh_output(args.output)
    groups = []
    for strategy in ("self_consumption", "peak_shaving", "carbon_aware"):
        runs = []
        for seed in range(args.seed, args.seed + args.scenarios):
            run_id = f"{strategy}-s{seed}"
            run_scenario(
                args.output,
                run_id,
                args.capacity_wh,
                strategy,
                seed,
                timeseries=not args.no_timeseries,
            )
            runs.append(run_id)
        groups.append((strategy, strategy.replace("_", " ").capitalize(), runs))
    write_study(
        args.output,
        "dispatch-comparison",
        "Probabilistic sampling",
        groups,
        run_parameters=["seed"],
        description=(
            "How much does a battery's dispatch strategy matter when demand is uncertain? "
            "Self-consumption, peak shaving, and carbon-aware dispatch each face the same "
            f"{args.scenarios} synthetic daily demand scenarios. "
            "Compare their costs, emissions, and peak grid imports, "
            "including how outcomes vary across scenarios."
        ),
    )
    print(f"View: python -m vessim view {args.output}")


if __name__ == "__main__":
    main()
