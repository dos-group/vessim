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
	cd viewer && [ -d node_modules ] || npm ci
	cd viewer && VITE_STATIC_BASE="./" npx vite build --outDir dist
	cp -r viewer/dist/. docs/viewer/
	uv run python examples/basic_example.py
	mkdir -p docs/viewer/results
	cp results/basic_example/metadata.yaml docs/viewer/results/
	cp results/basic_example/timeseries.csv docs/viewer/results/
	echo '{"mode":"single","experiments":[{"name":"","status":"completed"}]}' > docs/viewer/experiments.json
