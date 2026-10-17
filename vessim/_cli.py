"""Serve recorded experiments and studies in the Vessim viewer."""

from __future__ import annotations

import argparse
import functools
import gzip
import json
import sys
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from vessim._viewer import Catalog


def _viewer_dist_dir() -> Path:
    return Path(__file__).parent / "_viewer_dist"


class _ViewerHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, catalog: Catalog, viewer_dir: Path, **kwargs):
        self.catalog = catalog
        super().__init__(*args, directory=str(viewer_dir), **kwargs)

    def do_GET(self):
        path = unquote(urlsplit(self.path).path)
        if path == "/catalog.json":
            self._send(
                json.dumps(self.catalog.payload(), allow_nan=False).encode(), "application/json"
            )
        elif path.startswith("/data/"):
            parts = path.strip("/").split("/")
            try:
                if len(parts) != 3 or parts[2] != "trajectory":
                    raise KeyError(path)
                content, kind = self.catalog.trajectory(parts[1])
                self._send(content, kind)
            except (KeyError, OSError, ValueError):
                self.send_error(404, "Recorded trajectory is unavailable")
        else:
            super().do_GET()

    def _send(self, body: bytes, content_type: str) -> None:
        compressed = len(body) > 1024 and "gzip" in self.headers.get("Accept-Encoding", "")
        if compressed:
            body = gzip.compress(body, compresslevel=1)
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Vary", "Accept-Encoding")
        if compressed:
            self.send_header("Content-Encoding", "gzip")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def _cmd_view(args: argparse.Namespace) -> None:
    try:
        catalog = Catalog(Path(args.path))
        viewer_dir = _viewer_dist_dir()
        if not (viewer_dir / "index.html").exists():
            raise ValueError("Viewer assets not found. Run npm run build in viewer/.")
        if args.export:
            catalog.export(Path(args.export), viewer_dir)
            print(f"Static viewer exported to {args.export}")
            return
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    handler = functools.partial(_ViewerHandler, catalog=catalog, viewer_dir=viewer_dir)
    server = ThreadingHTTPServer(("localhost", args.port), handler)
    url = f"http://localhost:{server.server_port}"
    print(f"Experiment viewer: {url}\n{len(catalog.runs)} recorded runs · {catalog.source}")
    for error in catalog.errors:
        print(f"Skipped: {error}", file=sys.stderr)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main():
    parser = argparse.ArgumentParser(prog="vessim", description="Vessim CLI")
    sub = parser.add_subparsers(dest="command")
    view = sub.add_parser("view", help="Explore recorded experiments or a study")
    view.add_argument(
        "path", help="Experiment JSON/directory, collection directory, or study JSON"
    )
    view.add_argument("-p", "--port", type=int, default=8710)
    view.add_argument("--no-browser", action="store_true")
    view.add_argument("--export", metavar="DIRECTORY", help="Export a portable static viewer")
    args = parser.parse_args()
    if args.command == "view":
        _cmd_view(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
