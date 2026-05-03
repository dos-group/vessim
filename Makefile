.PHONY: docs docs-viewer serve-docs typecheck lint test check

check: typecheck lint test

typecheck:
	uv run mypy vessim

lint:
	uv run ruff check vessim

test:
	uv run pytest

docs: docs-viewer
	uv run mkdocs build

serve-docs: docs-viewer
	uv run mkdocs serve --watch docs

docs-viewer:
	cd viewer && [ -d node_modules ] || npm ci
	cd viewer && VITE_STATIC_BASE="./" npx vite build --outDir dist
	cp -r viewer/dist/. docs/viewer/
	uv run python examples/basic_example.py
	mkdir -p docs/viewer/results
	cp results/basic_example/metadata.yaml docs/viewer/results/
	cp results/basic_example/timeseries.csv docs/viewer/results/
	echo '{"mode":"single","experiments":[{"name":"","status":"completed"}]}' > docs/viewer/experiments.json
