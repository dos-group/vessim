"""Generate deterministic release fixtures without running simulations or using the network."""

import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from vessim._viewer import Catalog  # noqa: E402

DEST = ROOT / "results/viewer-release"
SOURCE = DEST / "input"
SOURCE.mkdir(parents=True, exist_ok=True)


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, separators=(",", ":")))


def record(identity, seed=42, amount=1, csv=None, multi=False):
    sites = ["North", "South", "West"] if multi else ["Microgrid 1"]
    return {
        "format": "vessim.experiment",
        "schema_version": 1,
        "run_id": identity,
        "parameters": {"battery_kwh": amount * 1000, "seed": seed, "days": 1},
        "config": {
            "environment": {"sim_start": "2026-01-01T00:00:00Z"},
            "microgrids": {
                site: {
                    "dispatchables": [
                        {"name": "grid", "type": "GridConnection"},
                        {"name": "battery", "type": "SimpleBattery"},
                    ]
                }
                for site in sites
            },
        },
        "execution": {"status": "completed", "steps": 24, "simulated_duration": 86400},
        "metrics": {
            "run": {"annual_cost": amount * 100.333},
            "microgrids": {
                site: {"grid_emissions": seed + amount, "grid_import": amount * 10000}
                for site in sites
            },
            "actors": {},
        },
        "metric_definitions": {
            "run": {"annual_cost": {"unit": "EUR", "description": "Synthetic annual net cost"}},
            "microgrids": {
                site: {
                    "grid_emissions": {"unit": "kgCO2e", "description": "Synthetic emissions"},
                    "grid_import": {"unit": "Wh"},
                }
                for site in sites
            },
            "actors": {},
        },
        "timeseries": csv,
    }


for study_id, name, repeated, multi in [
    ("comparison", "Equipment comparison", False, False),
    ("sampling", "Probabilistic sampling", True, False),
    ("multi", "Multiple microgrids", False, True),
]:
    directory = SOURCE / study_id
    groups = []
    for i in range(3):
        runs = []
        for seed in ([41, 42, 43] if repeated else [42]):
            identity = f"config-{i}-seed-{seed}"
            relative = f"runs/{identity}/experiment.json"
            doc = record(identity, seed, i + 1, "timeseries.csv", multi)
            # Repeated runs share configuration inputs, but have different outcomes.
            doc["metrics"]["run"]["annual_cost"] += seed * 0.01
            save(directory / relative, doc)
            lines = [
                "time,microgrid,p_delta,p_grid,dispatch_states.grid.current_power,dispatch_states.battery.current_power,dispatch_states.battery.soc"
            ]
            for hour in range(24):
                for site in doc["config"]["microgrids"]:
                    power = -100 * (i + 1) - seed + hour
                    lines.append(
                        f"2026-01-01T{hour:02}:00:00Z,{site},{power-10},{power},{power},10,{hour/24}"
                    )
            (directory / relative).with_name("timeseries.csv").write_text("\n".join(lines))
            runs.append({"path": relative})
        groups.append({"configuration_id": f"config-{i}", "name": f"Setup {i+1}", "runs": runs})
    save(
        directory / "study.json",
        {
            "format": "vessim.study",
            "schema_version": 2,
            "study_id": study_id,
            "name": name,
            "run_parameters": ["seed"],
            "configurations": groups,
        },
    )

large = SOURCE / "large"
shared = record("shared")
items = [
    {
        "run_id": f"run-{i}",
        "parameters": {"seed": i},
        "metrics": {
            "run": {"annual_cost": i * 0.3},
            "microgrids": {"Microgrid 1": {"grid_emissions": 10000 - i, "grid_import": i * 1000}},
            "actors": {},
        },
    }
    for i in range(10000)
]
save(
    large / "batch.json",
    {"format": "vessim.viewer.run-batch", "schema_version": 1, "shared": shared, "runs": items},
)
save(
    large / "study.json",
    {
        "format": "vessim.study",
        "schema_version": 2,
        "study_id": "large",
        "name": "10,000 summary runs",
        "run_parameters": ["seed"],
        "configurations": [{"configuration_id": "configuration", "run_batch": "batch.json"}],
    },
)
partial = SOURCE / "partial"
save(partial / "run/experiment.json", record("missing-recording", csv="absent.csv"))
save(
    partial / "study.json",
    {
        "format": "vessim.study",
        "schema_version": 2,
        "study_id": "partial",
        "name": "Partial data",
        "configurations": [
            {
                "configuration_id": "partial",
                "runs": [{"path": "missing.json"}, {"path": "run/experiment.json"}],
            }
        ],
    },
)
report = DEST / "report"
if report.exists():
    shutil.rmtree(report)
Catalog(SOURCE).export(report, ROOT / "vessim/_viewer_dist")
print(SOURCE)
