# Contributing

## Setup

Install dependencies (requires [uv](https://docs.astral.sh/uv/)):

```bash
uv pip install -e ".[dev,sil,docs]"
```

## Viewer

The viewer is a Vite/React app in `viewer/`.

### Local development

Install dependencies and start the dev server pointed at a local results directory:

```bash
cd viewer
npm ci
VITE_RESULTS_DIR=../results npm run dev
```

The viewer is then available at `http://localhost:5173`.

### Building

The viewer must be built before installing the Python package locally or running tests:

```bash
cd viewer && npm run build
```

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

### Embedded experiment viewer

The "Getting Started" page links to a live demo served from `docs/viewer/`. It is a static
viewer build with a checked-in results fixture. Rebuild it locally when the viewer source or
`examples/basic_example.py` changes:

```bash
make docs-viewer
```

## Release

1. Create a GitHub release (tag triggers the `publish.yml` workflow)
2. The workflow builds the viewer, bundles it into the Python package, and publishes to PyPI