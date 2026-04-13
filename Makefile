.PHONY: docs-viewer

docs-viewer:
	cd viewer && npm ci && VITE_STATIC_BASE="./" npx vite build --outDir dist
	cp -r viewer/dist/. docs/viewer/
	uv run python examples/basic_example.py
	mkdir -p docs/viewer/results
	cp results/basic_example/metadata.yaml docs/viewer/results/
	cp results/basic_example/timeseries.csv docs/viewer/results/
	echo '{"mode":"single","experiments":[{"name":"","status":"completed"}]}' > docs/viewer/experiments.json
