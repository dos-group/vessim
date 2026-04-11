.PHONY: docs-viewer

docs-viewer:
	cd viewer && npm ci && VITE_STATIC_BASE="/viewer/" npm run build
	cp -r viewer/dist/. docs/viewer/
	uv run python examples/basic_example.py
	cp results/basic_example/{metadata.yaml,timeseries.csv} docs/viewer/results/
	echo '{"mode":"single","experiments":[{"name":"","status":"completed"}]}' > docs/viewer/experiments.json
