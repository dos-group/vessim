"""Export the documentation gallery with the same assets and catalog as vessim view."""

import argparse
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from vessim._viewer import Catalog

ROOT = Path(__file__).resolve().parents[1]
STUDIES = (
    "getting-started",
    "infrastructure-year",
    "optuna-search",
    "dispatch-comparison",
    "multiple-microgrids",
)


def export_gallery(destination: Path, root: Path = ROOT) -> None:
    """Prepare a complete portable gallery before replacing generated docs output."""
    assets = root / "vessim/_viewer_dist"
    if not (assets / "index.html").is_file():
        raise ValueError("Build the viewer first: npm --prefix viewer run build")
    indexes = [root / "results/viewer-proposal" / identity / "study.json" for identity in STUDIES]
    replay = root / "results/viewer-proposal/optuna-2/study.json"
    if replay.exists():
        indexes.insert(3, replay)
    catalog = Catalog(root, study_paths=indexes)
    if catalog.errors:
        raise ValueError("Cannot publish incomplete examples: " + "; ".join(catalog.errors))
    # Portable examples must not disclose input filenames from the author's checkout.
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
    args = parser.parse_args()
    if args.output.exists() and args.output.resolve() != (ROOT / "docs/viewer").resolve():
        parser.error("Custom output directories must not already exist.")
    export_gallery(args.output)


if __name__ == "__main__":
    main()
