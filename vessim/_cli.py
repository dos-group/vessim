"""Vessim CLI

So far only supports:
- `vessim view <results-dir>`
"""

from __future__ import annotations

import argparse
import functools
import json
import sys
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

import yaml


def _viewer_dist_dir() -> Path:
    return Path(__file__).parent / "_viewer_dist"


class _ViewerHandler(SimpleHTTPRequestHandler):
    """Serves the built viewer app, /results/* files, and a /experiments JSON endpoint."""

    def __init__(self, *args, viewer_dir: Path, results_dir: Path, **kwargs):
        self.viewer_dir = viewer_dir
        self.results_dir = results_dir
        super().__init__(*args, **kwargs)

    def do_GET(self):
        url_path = self.path.split("?", 1)[0].split("#", 1)[0]
        if url_path == "/experiments":
            self._serve_experiments()
            return
        super().do_GET()

    def _serve_experiments(self):
        root_config = self.results_dir / "metadata.yaml"
        if root_config.exists():
            status = self._read_status(root_config)
            data = {"mode": "single", "experiments": [{"name": "", "status": status}]}
        else:
            experiments = []
            for subdir in sorted(self.results_dir.iterdir()):
                config_file = subdir / "metadata.yaml"
                if subdir.is_dir() and config_file.exists():
                    experiments.append({"name": subdir.name, "status": self._read_status(config_file)})
            data = {"mode": "multi", "experiments": experiments}

        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_status(self, config_file: Path) -> str | None:
        try:
            config = yaml.safe_load(config_file.read_text()) or {}
            return config.get("execution", {}).get("status")
        except Exception:
            return None

    def translate_path(self, path: str) -> str:
        # Strip query string and fragment
        path = path.split("?", 1)[0].split("#", 1)[0]

        if path.startswith("/results/"):
            rel = path[len("/results/"):]
            return str(self.results_dir / rel)
        if path == "/results":
            return str(self.results_dir)

        # Serve from viewer dist
        rel = path.lstrip("/")
        full = self.viewer_dir / rel
        # SPA fallback: if file doesn't exist, serve index.html
        if not full.exists() or full.is_dir():
            if rel and not (full.exists() and full.is_dir()):
                return str(self.viewer_dir / "index.html")
        return str(full)

    def log_message(self, format, *args):
        # Silence request logs
        pass


def _cmd_view(args: argparse.Namespace) -> None:
    results_dir = Path(args.directory).resolve()
    if not results_dir.is_dir():
        print(f"Error: '{results_dir}' is not a directory", file=sys.stderr)
        sys.exit(1)

    viewer_dir = _viewer_dist_dir()
    if not (viewer_dir / "index.html").exists():
        print("Error: viewer assets not found. Rebuild with `npm run build` in viewer/.",
              file=sys.stderr)
        sys.exit(1)

    port = args.port
    handler = functools.partial(
        _ViewerHandler,
        viewer_dir=viewer_dir,
        results_dir=results_dir,
    )
    server = HTTPServer(("localhost", port), handler)

    url = f"http://localhost:{port}"
    print(f"Serving experiment viewer at {url}")
    print(f"Results directory: {results_dir}")
    print("Press Ctrl+C to stop.\n")

    if not args.no_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


def main():
    parser = argparse.ArgumentParser(prog="vessim", description="Vessim CLI")
    sub = parser.add_subparsers(dest="command")

    view = sub.add_parser("view", help="View experiment results in the browser")
    view.add_argument("directory", help="Path to a results directory")
    view.add_argument("-p", "--port", type=int, default=8710, help="Port (default: 8710)")
    view.add_argument("--no-browser", action="store_true", help="Don't open browser automatically")

    args = parser.parse_args()
    if args.command == "view":
        _cmd_view(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
