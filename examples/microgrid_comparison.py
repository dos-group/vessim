"""Compare three independent microgrids under three shared equipment choices.

Each site has distinct synthetic weather, demand, and carbon intensity. There is
no electrical connection or workload migration between sites. All configurations
reuse the same site-specific input realizations. Run-level totals sum recorded
energy/emissions; coincident peak demand is accumulated from simultaneous states.

python examples/microgrid_comparison.py --output results/multiple-microgrids
"""

import argparse
from pathlib import Path

import vessim as vs
from infrastructure_study import inputs
from _common import fresh_output, write_study

SETUPS = {"grid-only": (0, 0), "renewables": (1500, 0), "with-storage": (1500, 3000)}


class CoincidentImportPeak(vs.Metric):
    """Record the maximum simultaneous aggregate grid-import power."""

    def __init__(self):
        super().__init__(
            "W",
            description="Maximum simultaneous sum of imported power across all microgrids",
            assumptions={"export_offset": False, "sampling": "hourly held states"},
        )

    def step(self, now, states, duration):
        self.value = max(self.value, sum(max(0, -state["p_grid"]) for state in states.values()))


def run_scenario(
    output: Path,
    run_id: str,
    solar_kw: float,
    battery_kwh: float,
    days: int = 7,
    seed: int = 42,
    timeseries: bool = True,
) -> vs.ExperimentResult:
    """Execute one three-microgrid configuration, preserving existing output."""
    if (output / run_id).exists():
        raise FileExistsError(f"Preserving existing run: {output / run_id}")
    with vs.Environment("2026-01-01", step_size=3600, name="Multiple microgrids") as env:
        metrics = {"coincident_import_peak": CoincidentImportPeak(), "grid_emissions": []}
        for index, scale in enumerate((0.7, 1.0, 1.3), start=1):
            name = f"Microgrid {index}"
            frame = inputs(days=days, seed=seed + index - 1)
            dispatchables = []
            if battery_kwh:
                dispatchables.append(
                    vs.SimpleBattery("battery", battery_kwh * 1000, initial_soc=0, c_rate=0.5)
                )
            dispatchables.append(vs.GridConnection())
            env.add_microgrid(
                [
                    vs.Consumer("datacenter", signal=vs.Trace(frame.load_kw * scale * 1000)),
                    vs.Producer("solar", signal=vs.Trace(frame.solar_cf * solar_kw * 1000)),
                    vs.Producer("wind", signal=vs.Trace(frame.wind_cf * solar_kw * 1000)),
                ],
                dispatchables=dispatchables,
                name=name,
                grid_signals={"carbon": vs.Trace(frame.carbon)},
            )
            metrics["grid_emissions"].append(vs.GridImportEmissions(name, "carbon"))
        recorder = env.add_controller(
            vs.Recorder(
                output / run_id,
                run_id=run_id,
                timeseries=timeseries,
                parameters={
                    "solar_kw_per_microgrid": solar_kw,
                    "wind_kw_per_microgrid": solar_kw,
                    "battery_kwh_per_microgrid": battery_kwh,
                    "days": days,
                    "seed": seed,
                    "step_seconds": 3600,
                },
                custom_metrics=metrics,
            )
        )
        env.run(days * 86400)
    result = recorder.result
    emissions = sum(grid["grid_emissions"] for grid in result.metrics["microgrids"].values())
    result.add_metric(
        "total_grid_emissions",
        emissions,
        "kgCO2e",
        description="Sum of grid-import emissions across three microgrids",
        assumptions={"source": "synthetic hourly intensities", "export_credit": False},
    )
    result.add_metric(
        "total_grid_import",
        sum(grid["grid_import"] for grid in result.metrics["microgrids"].values()),
        "Wh",
        description="Sum of imported electricity across three microgrids",
        assumptions={"export_offset": False},
    )
    result.save(output / run_id / "experiment.json")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("results/multiple-microgrids"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--no-timeseries", action="store_true")
    args = parser.parse_args()
    if args.seed < 0 or args.days < 1:
        parser.error("seed must be nonnegative and days must be positive")
    fresh_output(args.output)
    for name, (solar, battery) in SETUPS.items():
        run_scenario(
            args.output,
            name,
            solar,
            battery,
            days=args.days,
            seed=args.seed,
            timeseries=not args.no_timeseries,
        )
    write_study(
        args.output,
        "multiple-microgrids",
        "Multiple microgrids",
        [(name, name.replace("-", " ").capitalize(), [name]) for name in SETUPS],
        run_parameters=["seed"],
        description="Equipment choices for three sites with distinct demand and weather.",
    )
    print(f"View: python -m vessim view {args.output}")


if __name__ == "__main__":
    main()
