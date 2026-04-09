# Contributing

## Setup

Install dependencies (requires [uv](https://docs.astral.sh/uv/)):

```bash
uv pip install -e ".[dev,sil,docs]"
```

## Viewer

The viewer is a Vite/React app in `viewer/`. It must be built before running tests or packaging:

```bash
cd viewer && npm ci && npm run build
```

The built output is copied into `vessim/_viewer_dist/` at publish time (see `publish.yml`).

## Tests

```bash
uv run pytest          # unit tests
uv run mypy vessim     # type checking
uv run ruff check vessim  # linting
```

## Docs

```bash
uv run mkdocs serve    # live preview at http://127.0.0.1:8000
```

Docs are published automatically via [Read the Docs](https://vessim.readthedocs.io) on every push (config: `.readthedocs.yml`).

## Release

1. Create a GitHub release (tag triggers the `publish.yml` workflow)
2. The workflow builds the viewer, bundles it into the Python package, and publishes to PyPI