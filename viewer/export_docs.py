"""Build and export the examples with the same viewer used by vessim view."""

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from vessim._viewer import Catalog

ROOT = Path(__file__).resolve().parents[1]
STUDIES = (
    "getting-started",
    "infrastructure-year",
    "optuna-search",
    "dispatch-comparison",
)


def export_gallery(destination: Path, source: Path, root: Path = ROOT) -> None:
    """Validate all published examples before replacing the generated docs gallery."""
    assets = root / "vessim/_viewer_dist"
    if not (assets / "index.html").is_file():
        raise ValueError("Build the viewer first: npm --prefix viewer run build")
    indexes = [source / identity / "study.json" for identity in STUDIES]
    catalog = Catalog(source, study_paths=indexes)
    if catalog.errors:
        raise ValueError("Cannot publish incomplete examples: " + "; ".join(catalog.errors))
    for run in catalog.runs:
        run["record"]["config"] = json.loads(
            json.dumps(run["record"]["config"]).replace(f"{root.as_posix()}/", "")
        )
    with TemporaryDirectory() as temporary:
        bundle = Path(temporary) / "viewer"
        catalog.export(bundle, assets)
        exported = json.loads((bundle / "catalog.json").read_text())
        if exported["errors"]:
            raise ValueError("Cannot publish missing recordings: " + "; ".join(exported["errors"]))
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(bundle, destination)
    print(f"Exported {len(catalog.studies)} studies and {len(catalog.runs)} runs to {destination}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/viewer")
    parser.add_argument("--source", type=Path, help="Export an already generated example gallery")
    parser.add_argument("--trials", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.output.exists() and args.output.resolve() != (ROOT / "docs/viewer").resolve():
        parser.error("Custom output directories must not already exist.")
    if args.source:
        export_gallery(args.output, args.source)
    else:
        with TemporaryDirectory() as temporary:
            source = Path(temporary) / "gallery"
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "examples/build_gallery.py"),
                    "--output",
                    str(source),
                    "--trials",
                    str(args.trials),
                    "--seed",
                    str(args.seed),
                ],
                check=True,
            )
            export_gallery(args.output, source)


if __name__ == "__main__":
    main()
