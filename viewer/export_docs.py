"""Rebuild the generated documentation viewer with the same static export path."""

from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from vessim._cli import _viewer_dist_dir
from vessim._viewer import Catalog

root = Path(__file__).resolve().parents[1]
with TemporaryDirectory() as temporary:
    destination = Path(temporary) / "viewer"
    Catalog(root / "results/strategy-comparison").export(
        destination, _viewer_dist_dir()
    )
    shutil.copytree(destination, root / "docs/viewer", dirs_exist_ok=True)
