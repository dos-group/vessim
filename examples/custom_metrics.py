"""Evaluate energy, cost, and emissions with custom optimization objectives.

python examples/custom_metrics.py
All prices and equipment figures below are illustrative assumptions.
"""

import numpy as np
import pandas as pd

import vessim as vs


class HighImportDuration(vs.Metric):
    """Count hours above a chosen grid-import threshold."""

    def __init__(self, microgrid, threshold_w):
        super().__init__(
            "h",
            microgrid=microgrid,
            description="Time above the grid-import threshold",
            assumptions={"threshold_w": threshold_w},
        )
        self.threshold_w = threshold_w

    def step(self, now, states, duration):
        if -states[self.microgrid]["p_grid"] > self.threshold_w:
            self.value += duration / 3600


def main():
    seconds = np.arange(0, 86401, 300)
    solar = vs.Trace(
        pd.Series(
            5000 * np.maximum(0, np.sin((seconds / 3600 - 6) * np.pi / 12)),
            index=seconds,
        )
    )
    capacity_wh = 1500
    with vs.Environment("2026-01-01", step_size=300) as env:
        env.add_microgrid(
            name="site",
            actors=[
                vs.Producer("solar", signal=solar),
                vs.Consumer("server", signal=700),
            ],
            dispatchables=[
                vs.SimpleBattery("battery", capacity_wh, initial_soc=0.5),
                vs.GridConnection(),
            ],
            grid_signals={
                "buy_price": 0.30,  # EUR/kWh
                "sell_price": 0.08,  # EUR/kWh
                "carbon": 0.25,  # kgCO2e/kWh
            },
        )
        recorder = env.add_controller(
            vs.Recorder(
                "results/custom_metrics",
                timeseries=False,
                parameters={"battery_capacity_wh": capacity_wh},
                custom_metrics={
                    "electricity_import_cost": vs.ElectricityImportCost("site", "buy_price"),
                    "electricity_export_revenue": vs.ElectricityExportRevenue(
                        "site", "sell_price"
                    ),
                    "grid_import_emissions": vs.GridImportEmissions("site", "carbon"),
                    "high_import_duration": HighImportDuration("site", 500),
                },
            )
        )
        env.run(24 * 3600)

    result = recorder.result
    result.add_metric(
        "battery_capex", capacity_wh / 1000 * 400, "EUR", assumptions={"battery_eur_per_kwh": 400}
    )
    result.add_metric(
        "battery_embodied_emissions",
        capacity_wh / 1000 * 100,
        "kgCO2e",
        assumptions={"battery_kgco2e_per_kwh": 100},
    )
    result.add_metric("area", 25, "m2", microgrid="site", actor="solar")
    grid = result.metrics["microgrids"]["site"]
    result.add_metric(
        "net_electricity_cost",
        grid["electricity_import_cost"] - grid["electricity_export_revenue"],
        "EUR",
        microgrid="site",
        description="Electricity import cost less export revenue",
    )
    result.save("results/custom_metrics/experiment.json")
    # Pass plain numbers to an optimizer. Weighting and constraints stay in the caller.
    objectives = [
        result.metrics["run"]["battery_capex"],
        grid["net_electricity_cost"],
        grid["grid_import_emissions"],
    ]
    area_constraint = result.metrics["actors"]["site"]["solar"]["area"] - 30
    print("Objectives:", objectives)
    print("Area constraint (feasible when <= 0):", area_constraint)


if __name__ == "__main__":
    main()
