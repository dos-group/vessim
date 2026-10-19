"""Run the four published examples using their normal command-line interfaces.

python examples/build_gallery.py --output results/gallery
python -m vessim view results/gallery
"""

import argparse
from pathlib import Path
import subprocess
import sys

from _common import fresh_output

EXAMPLES = Path(__file__).resolve().parent


def build(output: Path, trials: int = 100, seed: int = 42):
    if trials < 1 or seed < 0:
        raise ValueError("trials must be positive and seed must be nonnegative")
    # Check optional tooling before starting the simulations.
    import optuna  # noqa: F401

    fresh_output(output)
    commands = [
        ("basic_example.py", "getting-started", []),
        ("infrastructure_study.py", "infrastructure-year", ["--seed", str(seed)]),
        (
            "infrastructure_study.py",
            "optuna-search",
            ["--seed", str(seed), "--trials", str(trials), "--financial"],
        ),
        ("strategy_comparison.py", "dispatch-comparison", ["--seed", str(seed)]),
    ]
    for script, name, options in commands:
        print(f"Running {name}", flush=True)
        subprocess.run(
            [sys.executable, str(EXAMPLES / script), "--output", str(output / name), *options],
            check=True,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("results/gallery"))
    parser.add_argument("--trials", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    build(args.output, args.trials, args.seed)


if __name__ == "__main__":
    main()
