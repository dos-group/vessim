.PHONY: docs docs-viewer serve-docs typecheck lint test check

CHECK_RUN = uv run --extra dev --extra live --extra mosaik

check: typecheck lint test

typecheck:
	$(CHECK_RUN) mypy vessim

lint:
	$(CHECK_RUN) ruff check vessim

test:
	$(CHECK_RUN) pytest

docs: docs-viewer
	uv run --extra docs mkdocs build

serve-docs: docs-viewer
	uv run --extra docs mkdocs serve --watch docs

docs-viewer:
	npm --prefix viewer ci
	npm --prefix viewer run build
	uv run python examples/strategy_comparison.py
	uv run python viewer/export_docs.py
